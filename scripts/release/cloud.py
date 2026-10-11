"""Robot-only provider boundaries and sanitized deployment receipts.

No provisioning, paid plan changes, database bootstrap or physical control.
"""

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from evidence import REPOSITORY, Rejected, digest, require, save, verify_stage


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def provider(url, token, payload=None):
    require(token, "Provider credential missing")
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode() if payload is not None else None,
        method="PUT" if payload is not None else "GET",
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=45
        ) as response:
            return json.loads(response.read(1024 * 1024))
    except (urllib.error.URLError, ValueError, TimeoutError):
        raise Rejected(
            "Provider readback unavailable; inspect private provider logs"
        ) from None


def origin(value, suffix=None):
    parsed = urllib.parse.urlsplit(value)
    require(
        parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.port
        and not parsed.query
        and not parsed.fragment
        and parsed.path in {"", "/"},
        "Expected credential-free HTTPS origin",
    )
    if suffix:
        require(parsed.hostname.endswith(suffix), "Unexpected deployment host")
    return value.rstrip("/")


def staging_storage(values):
    mode = os.environ.get("ROBOT_STORAGE_MODE", "ephemeral-simulation")
    require(mode in {"ephemeral-simulation", "turso"}, "Unknown staging storage mode")
    require(values.get("ROBOT_STORAGE_MODE") == mode, "Staging storage binding mismatch")
    if mode == "turso":
        expected = os.environ.get("ROBOT_TURSO_DATABASE_URL", "")
        parsed = urllib.parse.urlsplit(expected)
        require(
            parsed.scheme == "libsql" and parsed.hostname
            and re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.turso\.io", parsed.hostname)
            and not parsed.username and not parsed.password and not parsed.port
            and not parsed.query and not parsed.fragment and parsed.path in {"", "/"},
            "Configure the reviewed staging Turso database origin",
        )
        require(values.get("ROBOT_TURSO_DATABASE_URL") == expected,
                "Turso staging database identity mismatch")
        require(bool(values.get("ROBOT_TURSO_AUTH_TOKEN")), "Turso runtime credential missing")
    return mode


def preflight(environment):
    require(environment in {"Staging", "Production"}, "Unknown environment")
    require(
        os.environ["GITHUB_REF"] == "refs/heads/main", "Cloud release requires main"
    )
    service_id = os.environ.get("RENDER_SERVICE_ID", "")
    require(
        re.fullmatch(r"srv-[A-Za-z0-9]+", service_id),
        "Configure isolated Render service ID",
    )
    token = os.environ.get("RENDER_API_KEY", "")
    base = "https://api.render.com/v1/services/" + service_id
    service = provider(base, token)
    require(
        service.get("repo") == "https://github.com/" + REPOSITORY
        and service.get("branch") == "main"
        and service.get("type") == "web_service"
        and service.get("rootDir") == "onesa-ai-robot-backend",
        "Render repository, branch or backend root mismatch",
    )
    require(
        service.get("autoDeployTrigger") == "off" or service.get("autoDeploy") == "no",
        "Render native auto-deploy must be off",
    )
    details = service.get("serviceDetails", {})
    require(
        details.get("env") == "docker",
        "Render must use the reviewed backend Dockerfile",
    )
    require(
        origin(details.get("url", "")) == origin(os.environ.get("ROBOT_API_URL", "")),
        "Render API URL binding mismatch",
    )
    entries = provider(base + "/env-vars?limit=100", token)
    require(
        isinstance(entries, list) and len(entries) < 100,
        "Complete environment readback needed",
    )
    values = {entry["envVar"]["key"]: entry["envVar"]["value"] for entry in entries}
    require(
        values.get("ROBOT_ACTUATION_ENABLED") == "false",
        "Physical operation must be disabled",
    )
    require(
        values.get("ROBOT_DEPLOYMENT_ENVIRONMENT") == environment.lower(),
        "Environment mismatch",
    )
    require(
        values.get("ROBOT_DATABASE_PATH") == "/app/storage/robot.sqlite3",
        "Isolated database required",
    )
    require(
        values.get("ROBOT_OPERATOR_PASSWORD_HASH", "").startswith("scrypt$"),
        "Operator auth missing",
    )
    if environment == "Staging":
        require(
            details.get("plan") == "free", "Staging uses only an approved free service"
        )
        staging_storage(values)
        require(
            os.environ.get("ROBOT_TEST_OPERATOR") == values.get("ROBOT_OPERATOR_NAME"),
            "Dedicated synthetic staging operator missing",
        )
    else:
        # Current Free Render architecture cannot satisfy this. No paid upgrade is attempted.
        require(
            details.get("plan") == "free"
            and details.get("disk", {}).get("mountPath") == "/app/storage",
            "Production BLOCKED: free Render has no durable SQLite volume; owner storage decision required",
        )
        require(
            values.get("ROBOT_STORAGE_MODE") == "persistent",
            "Durable production storage required",
        )
        require(
            origin(values.get("ROBOT_PUBLIC_ORIGIN", ""))
            == origin(os.environ["ROBOT_PUBLIC_ORIGIN"]),
            "Production operator origin mismatch",
        )
    project = os.environ.get("VERCEL_PROJECT_ID", "")
    team = os.environ.get("VERCEL_ORG_ID", "")
    require(
        re.fullmatch(r"prj_[A-Za-z0-9]+", project)
        and re.fullmatch(r"(?:team|user)_[A-Za-z0-9]+", team),
        "Vercel project/team binding missing",
    )
    query = urllib.parse.urlencode({"teamId": team})
    data = provider(
        "https://api.vercel.com/v9/projects/" + project + "?" + query,
        os.environ.get("VERCEL_TOKEN", ""),
    )
    link = data.get("link", {})
    require(
        link.get("org") == "DruHustle"
        and link.get("repo") == "onesa-ai-robot"
        and data.get("rootDirectory") == "onesa-ai-robot-frontend",
        "Vercel root/repository mismatch",
    )
    if environment == "Staging":
        require(
            (data.get("ssoProtection") or {}).get("deploymentType")
            in {
                "all",
                "all_except_custom_domains",
                "preview",
                "prod_deployment_urls_and_all_previews",
            }
            and os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET"),
            "Protected Preview required",
        )
    envs = provider(
        "https://api.vercel.com/v9/projects/"
        + project
        + "/env?"
        + query
        + "&decrypt=true",
        os.environ["VERCEL_TOKEN"],
    )
    target = "preview" if environment == "Staging" else "production"
    matching = [
        item
        for item in envs.get("envs", [])
        if item.get("key") == "ROBOT_API_URL"
        and target in item.get("target", [])
        and item.get("gitBranch") in {None, "main"}
    ]
    require(
        len(matching) == 1
        and origin(matching[0].get("value", "")) == origin(os.environ["ROBOT_API_URL"]),
        "Server-only frontend API origin must match its isolated Render target",
    )
    return service_id


def frontend(url, environment):
    url = origin(url, ".vercel.app" if environment == "Staging" else None)
    query = urllib.parse.urlencode({"teamId": os.environ["VERCEL_ORG_ID"]})
    data = provider(
        "https://api.vercel.com/v13/deployments/" + url.split("//")[1] + "?" + query,
        os.environ["VERCEL_TOKEN"],
    )
    require(
        data.get("projectId") == os.environ["VERCEL_PROJECT_ID"]
        and data.get("readyState") == "READY"
        and data.get("meta", {}).get("githubCommitSha") == os.environ["GITHUB_SHA"]
        and (data.get("target") == "production") == (environment == "Production"),
        "Vercel exact-candidate verification failed",
    )
    return data["id"]


def receipt(environment, directory, browser):
    directory = Path(directory)
    record = json.loads((directory / "preflight.json").read_text())
    url = origin((directory / "frontend-url.txt").read_text().strip(), ".vercel.app")
    vercel_id = frontend(url, environment)
    if environment == "Production":
        operator_url = origin((directory / "operator-url.txt").read_text().strip())
        require(
            frontend(operator_url, environment) == vercel_id, "Production alias changed"
        )
    render = json.loads((directory / "render.json").read_text())
    base = "https://api.render.com/v1/services/" + os.environ["RENDER_SERVICE_ID"]
    deploy = provider(
        base + "/deploys/" + render["deployment_id"], os.environ["RENDER_API_KEY"]
    )
    latest = provider(base + "/deploys?limit=1", os.environ["RENDER_API_KEY"])
    require(
        deploy.get("status") == "live"
        and deploy.get("commit", {}).get("id") == os.environ["GITHUB_SHA"]
        and latest
        and latest[0].get("deploy", latest[0]).get("id") == render["deployment_id"],
        "Render exact-candidate verification failed",
    )
    suite = json.loads((directory / "smoke.json").read_text())
    require(
        suite["scope"] == "software-simulation-only" and suite["status"] == "PASS",
        "Simulator smoke failed",
    )
    checks = dict(suite["checks"])
    checks["deployed_commit"] = "PASS"
    checks["browser_acceptance"] = "PASS" if browser else "BLOCKED"
    result = {
        "repository": REPOSITORY,
        "candidate_commit": os.environ["GITHUB_SHA"],
        "source_sha256": record.get(
            "valid_for_source_sha256", record.get("source_sha256")
        ),
        "environment": environment,
        "builds_sha256": digest(record["builds"]),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "render_deployment_id": render["deployment_id"],
        "vercel_deployment_id": vercel_id,
        "scope": "software-simulation-only",
        "storage": os.environ.get("ROBOT_STORAGE_MODE", "ephemeral-simulation")
        if environment == "Staging" else "persistent",
        "physical_hardware_approved": False,
        "frontend_url": url,
        "operator_url": operator_url if environment == "Production" else url,
        "render_service_id": os.environ["RENDER_SERVICE_ID"],
        "status": "PASS"
        if all(value == "PASS" for value in checks.values())
        else "BLOCKED",
    }
    if environment == "Staging":
        verify_stage(
            result,
            result["candidate_commit"],
            result["source_sha256"],
            record["builds"],
        )
    save(result, directory / "record.json")
    require(result["status"] == "PASS", "Deployment acceptance blocked")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=["preflight", "bind-preview", "operator-origin", "receipt"]
    )
    parser.add_argument("environment", choices=["Staging", "Production"])
    parser.add_argument("--directory")
    parser.add_argument("--browser-passed", action="store_true")
    args = parser.parse_args()
    if args.mode == "preflight":
        preflight(args.environment)
    elif args.mode == "bind-preview":
        require(
            args.environment == "Staging", "Only synthetic Preview may change origin"
        )
        service = preflight(args.environment)
        url = origin(
            Path(args.directory, "frontend-url.txt").read_text().strip(), ".vercel.app"
        )
        frontend(url, args.environment)
        provider(
            "https://api.render.com/v1/services/"
            + service
            + "/env-vars/ROBOT_PUBLIC_ORIGIN",
            os.environ["RENDER_API_KEY"],
            {"value": url},
        )
    elif args.mode == "operator-origin":
        require(
            args.environment == "Production",
            "Canonical operator origin is production-only",
        )
        directory = Path(args.directory)
        deployed = origin(
            (directory / "frontend-url.txt").read_text().strip(), ".vercel.app"
        )
        canonical = origin(os.environ["ROBOT_PUBLIC_ORIGIN"])
        require(
            frontend(deployed, "Production") == frontend(canonical, "Production"),
            "Canonical production origin does not serve the reviewed deployment",
        )
        (directory / "operator-url.txt").write_text(canonical)
    else:
        receipt(args.environment, args.directory, args.browser_passed)


if __name__ == "__main__":
    try:
        main()
    except (Rejected, KeyError, ValueError, OSError, TypeError):
        raise SystemExit(
            "Robot cloud operation blocked; inspect configuration and private provider logs"
        ) from None
