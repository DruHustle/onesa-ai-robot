"""Fence only the stopped, existing synthetic staging journal before a rolling deploy."""

import http.cookiejar
import json
import os
import re
import urllib.request

from cloud import NoRedirect, origin, provider
from evidence import REPOSITORY, Rejected, require
from staging_configuration import API, SERVICE, TURSO, target

LEASE = "robot_simulation_lease_v1"


def staging_context():
    require(
        os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
        and os.environ.get("GITHUB_REF") == "refs/heads/staging"
        and os.environ.get("GITHUB_ACTOR") == "DruHustle"
        and os.environ.get("GITHUB_TRIGGERING_ACTOR") == "DruHustle"
        and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and os.environ.get("RENDER_SERVICE_ID") == SERVICE,
        "Owner-hosted synthetic staging handoff required",
    )


def sql_call(token, sql, arguments=()):
    request = urllib.request.Request(
        "https://onesa-ai-robot-backend-staging-druhustle.aws-eu-west-1.turso.io/v2/pipeline",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "requests": [
                    {
                        "type": "execute",
                        "stmt": {
                            "sql": sql,
                            "args": [
                                {"type": "text", "value": value} for value in arguments
                            ],
                        },
                    },
                    {"type": "close"},
                ]
            }
        ).encode(),
    )
    with urllib.request.build_opener(NoRedirect()).open(
        request, timeout=15
    ) as response:
        require(response.status == 200, "Journal handoff transport failed")
        raw = response.read(65537)
        require(len(raw) <= 65536, "Journal handoff response exceeds limit")
        result = json.loads(raw)["results"]
    require(
        len(result) == 2 and all(item["type"] == "ok" for item in result),
        "Journal handoff statement failed",
    )
    require(result[1]["response"]["type"] == "close", "Journal connection must close")
    value = result[0]["response"]
    require(value["type"] == "execute", "Unexpected journal response")
    columns = [column["name"] for column in value["result"]["cols"]]
    rows = []
    for row in value["result"]["rows"]:
        require(
            all(cell["type"] in {"text", "integer"} for cell in row),
            "Unexpected journal value",
        )
        rows.append(
            dict(
                zip(
                    columns,
                    [
                        int(cell["value"])
                        if cell["type"] == "integer"
                        else cell["value"]
                        for cell in row
                    ],
                    strict=True,
                )
            )
        )
    return rows


def fence_stopped_lease(token, execute=sql_call):
    rows = execute(
        token, f"SELECT owner,expires>unixepoch() AS active FROM {LEASE} WHERE id=1"
    )
    require(
        len(rows) == 1 and re.fullmatch(r"[a-f0-9]{32}", rows[0].get("owner", "")),
        "Existing staging lease identity required",
    )
    owner = rows[0]["owner"]
    if rows[0]["active"] == 1:
        changed = execute(
            token,
            f"UPDATE {LEASE} SET expires=unixepoch()-1 WHERE id=1 AND owner=? RETURNING owner",
            (owner,),
        )
        require(
            changed == [{"owner": owner}],
            "Journal owner changed; preserve the new owner",
        )
    verified = execute(
        token, f"SELECT owner,expires>unixepoch() AS active FROM {LEASE} WHERE id=1"
    )
    require(verified == [{"owner": owner, "active": 0}], "Journal handoff not verified")


def handoff():
    staging_context()
    token = os.environ.get("RENDER_API_KEY", "")
    base = "https://api.render.com/v1/services/" + SERVICE
    service = provider(base, token)
    target(service, require_docker=False)
    require(
        service.get("branch") == "staging"
        and service.get("autoDeployTrigger") == "off",
        "Isolated staging branch required",
    )
    entries = provider(base + "/env-vars?limit=100", token)
    require(
        isinstance(entries, list) and len(entries) < 100,
        "Complete staging environment required",
    )
    values = {entry["envVar"]["key"]: entry["envVar"]["value"] for entry in entries}
    require(
        values.get("ROBOT_DEPLOYMENT_ENVIRONMENT") == "staging"
        and values.get("ROBOT_ACTUATION_ENABLED") == "false",
        "Physical operation prohibited",
    )
    if values.get("ROBOT_STORAGE_MODE") != "turso":
        return {"scope": "staging", "remote_lease_handoff_required": False}
    require(
        values.get("ROBOT_TURSO_DATABASE_URL") == TURSO
        and bool(values.get("ROBOT_TURSO_AUTH_TOKEN")),
        "Verified staging journal required",
    )
    public_origin = origin(values.get("ROBOT_PUBLIC_ORIGIN", ""), ".vercel.app")
    password = os.environ.get("ROBOT_TEST_PASSWORD", "")
    name = os.environ.get("ROBOT_TEST_OPERATOR", "")
    require(
        bool(password) and name == values.get("ROBOT_OPERATOR_NAME"),
        "Existing operator credentials required",
    )
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPCookieProcessor(jar)
    )

    def api(route, body=None, csrf=""):
        headers = {"Origin": public_origin, "Content-Type": "application/json"}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        request = urllib.request.Request(
            API + route,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        with opener.open(request, timeout=45) as response:
            require(response.status == 200, "Staging operator handoff rejected")
            return json.loads(response.read(65536))

    login = api("/api/v1/auth/login", {"name": name, "password": password})
    csrf = login["csrf"]
    try:
        api("/api/v1/stop", {}, csrf)
        status = api("/api/v1/status")
        require(
            status.get("mode") == "simulation"
            and status.get("physical_actuation") is False
            and status.get("stopped") is True
            and status.get("active_task") is None,
            "Stopped simulation required before handoff",
        )
        # This authenticated read flushes pending history before authority is expired.
        require(
            all(task["state"] != "running" for task in api("/api/v1/tasks")["tasks"]),
            "Pending running history must drain",
        )
    finally:
        api("/api/v1/auth/logout", {}, csrf)
    fence_stopped_lease(values["ROBOT_TURSO_AUTH_TOKEN"])
    return {
        "scope": "staging",
        "simulation_stopped": True,
        "journal_lease_expired": True,
        "history_preserved": True,
        "credentials_changed": False,
        "production_modified": False,
        "physical_actuation": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(handoff()))
    except (Rejected, KeyError, ValueError, TypeError, OSError):
        raise SystemExit(
            "Staging journal handoff failed; no credentials or provider response emitted"
        ) from None
