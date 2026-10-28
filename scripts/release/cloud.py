"""Robot-only provider boundaries and sanitized deployment receipts.

No provisioning, paid plan changes, database bootstrap or physical control.
"""

import argparse
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from evidence import REPOSITORY, GitHub, Rejected, digest, require, save, verify_stage
from service_runtime import allowed as runtime_allowed
from service_runtime import kind as runtime_kind
from service_runtime import verified as runtime_verified

PRODUCTION_SERVICE = "srv-db5k88flk1mc73aa9110"
PRODUCTION_DATABASE = "libsql://onesa-ai-robot-backend-druhustle.aws-eu-west-1.turso.io"
STAGING_DATABASE = (
    "libsql://onesa-ai-robot-backend-staging-druhustle.aws-eu-west-1.turso.io"
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def provider(url, token, payload=None, *, method=None):
    require(token, "Provider credential missing")
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method or ("PUT" if payload is not None else "GET"),
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
    require(
        values.get("ROBOT_STORAGE_MODE") == mode, "Staging storage binding mismatch"
    )
    if mode == "turso":
        expected = os.environ.get("ROBOT_TURSO_DATABASE_URL", "")
        parsed = urllib.parse.urlsplit(expected)
        require(
            parsed.scheme == "libsql"
            and parsed.hostname
            and re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.turso\.io", parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.port
            and not parsed.query
            and not parsed.fragment
            and parsed.path in {"", "/"},
            "Configure the reviewed staging Turso database origin",
        )
        require(
            values.get("ROBOT_TURSO_DATABASE_URL") == expected,
            "Turso staging database identity mismatch",
        )
        require(
            bool(values.get("ROBOT_TURSO_AUTH_TOKEN")),
            "Turso runtime credential missing",
        )
    return mode


def filesystem_required(environment, storage_mode):
    return storage_mode != "turso"


def production_storage(values, staging_values):
    require(
        os.environ.get("ROBOT_STORAGE_MODE")
        == values.get("ROBOT_STORAGE_MODE")
        == "turso"
        and os.environ.get("ROBOT_TURSO_DATABASE_URL")
        == values.get("ROBOT_TURSO_DATABASE_URL")
        == PRODUCTION_DATABASE
        and bool(values.get("ROBOT_TURSO_AUTH_TOKEN")),
        "Approved production Turso binding and credential required",
    )
    require(
        staging_values.get("ROBOT_DEPLOYMENT_ENVIRONMENT") == "staging"
        and staging_values.get("ROBOT_TURSO_DATABASE_URL") == STAGING_DATABASE
        and bool(staging_values.get("ROBOT_TURSO_AUTH_TOKEN"))
        and bool(staging_values.get("ROBOT_OPERATOR_PASSWORD_HASH"))
        and values["ROBOT_TURSO_AUTH_TOKEN"] != staging_values["ROBOT_TURSO_AUTH_TOKEN"]
        and values.get("ROBOT_OPERATOR_PASSWORD_HASH")
        != staging_values["ROBOT_OPERATOR_PASSWORD_HASH"],
        "Production database and operator credentials must be isolated from staging",
    )
    return "turso"


def preflight(environment):
    require(environment in {"Staging", "Production"}, "Unknown environment")
    require(
        os.environ["GITHUB_REF"]
        == ("refs/heads/staging" if environment == "Staging" else "refs/heads/main"),
        "Cloud release branch mismatch",
    )
    service_id = os.environ.get("RENDER_SERVICE_ID", "")
    require(
        re.fullmatch(r"srv-[A-Za-z0-9]+", service_id),
        "Configure isolated Render service ID",
    )
    if environment == "Staging":
        require(
            service_id == "srv-db5k9ft9fdbs73d622cg",
            "Identified staging service required",
        )
    else:
        require(
            service_id == PRODUCTION_SERVICE, "Identified production service required"
        )
    token = os.environ.get("RENDER_API_KEY", "")
    base = "https://api.render.com/v1/services/" + service_id
    service = provider(base, token)
    require(
        service.get("repo")
        in {
            "https://github.com/" + REPOSITORY,
            "https://github.com/" + REPOSITORY + ".git",
        }
        and service.get("branch") == ("staging" if environment == "Staging" else "main")
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
        runtime_verified(service),
        "Reviewed backend runtime and layout required",
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
        runtime_kind(service) != "python"
        or values.get("ROBOT_STORAGE_MODE") == "turso",
        "Native runtime requires reviewed durable Turso journal",
    )
    require(
        values.get("ROBOT_ACTUATION_ENABLED") == "false",
        "Physical operation must be disabled",
    )
    require(
        values.get("ROBOT_DEPLOYMENT_ENVIRONMENT") == environment.lower(),
        "Environment mismatch",
    )
    if filesystem_required(environment, values.get("ROBOT_STORAGE_MODE")):
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
        if values.get("ROBOT_STORAGE_MODE") == "turso":
            require(
                details.get("plan") == "free" and details.get("region") == "frankfurt",
                "Identified free Frankfurt production runtime required",
            )
            staging_entries = provider(
                "https://api.render.com/v1/services/srv-db5k9ft9fdbs73d622cg/env-vars?limit=100",
                token,
            )
            require(
                isinstance(staging_entries, list) and len(staging_entries) < 100,
                "Complete staging isolation readback needed",
            )
            production_storage(
                values,
                {
                    entry["envVar"]["key"]: entry["envVar"]["value"]
                    for entry in staging_entries
                },
            )
        else:
            require(
                details.get("plan") == "free"
                and details.get("disk", {}).get("mountPath") == "/app/storage"
                and values.get("ROBOT_STORAGE_MODE") == "persistent",
                "Production BLOCKED: free Render has no durable SQLite volume; approved remote storage required",
            )
        require(
            origin(values.get("ROBOT_PUBLIC_ORIGIN", ""))
            == origin(os.environ["ROBOT_PUBLIC_ORIGIN"]),
            "Production operator origin mismatch",
        )
    require(
        runtime_allowed(
            service,
            environment,
            durable_remote=values.get("ROBOT_STORAGE_MODE") == "turso",
        ),
        "Reviewed backend runtime and layout required",
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
        and link.get("repo") == "onesa-robot"
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
        and item.get("gitBranch")
        in ({"staging"} if environment == "Staging" else {None, "main"})
    ]
    require(
        len(matching) == 1
        and origin(matching[0].get("value", "")) == origin(os.environ["ROBOT_API_URL"]),
        "Server-only frontend API origin must match its isolated Render target",
    )
    if environment == "Staging":
        from edge_fixture import remember

        remember(values)
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


def resolve_preview(directory, *, attempts=60):
    """Reuse native Git's exact protected staging build; never deploy it twice."""
    preflight("Staging")
    query = urllib.parse.urlencode(
        {
            "projectId": os.environ["VERCEL_PROJECT_ID"],
            "teamId": os.environ["VERCEL_ORG_ID"],
            "limit": 100,
        }
    )
    for attempt in range(attempts):
        data = provider(
            "https://api.vercel.com/v6/deployments?" + query, os.environ["VERCEL_TOKEN"]
        )
        candidates = [
            item
            for item in data.get("deployments", [])
            if item.get("meta", {}).get("githubCommitSha") == os.environ["GITHUB_SHA"]
            and item.get("meta", {}).get("githubCommitRef") == "staging"
            and item.get("target") in {None, "preview"}
        ]
        ready = [
            item
            for item in candidates
            if item.get("readyState", item.get("state")) == "READY"
        ]
        if ready:
            require(
                len(ready) == 1, "Multiple native staging Previews for the same source"
            )
            url = origin("https://" + ready[0]["url"], ".vercel.app")
            frontend(url, "Staging")
            Path(directory, "frontend-url.txt").write_text(url + "\n")
            print("Verified exact-source protected native Git staging Preview")
            return url
        require(
            not any(
                item.get("readyState", item.get("state")) in {"ERROR", "CANCELED"}
                for item in candidates
            ),
            "Native staging Preview build failed",
        )
        if attempt + 1 < attempts:
            time.sleep(5)
    raise Rejected("No ready native Git staging Preview for the exact candidate")


def receipt(environment, directory, browser):
    directory = Path(directory)
    record = json.loads((directory / "preflight" / "record.json").read_text())
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
    selected = selected_components(directory, environment)
    backend_sha = selected["backend_commit"] if selected else os.environ["GITHUB_SHA"]
    require(
        deploy.get("status") == "live"
        and deploy.get("commit", {}).get("id") == backend_sha
        and latest
        and latest[0].get("deploy", latest[0]).get("id") == render["deployment_id"],
        "Render exact-candidate verification failed",
    )
    suite = json.loads((directory / "smoke.json").read_text())
    require(
        suite["scope"] == "software-simulation-only"
        and suite["status"] in {"PASS", "FAIL", "BLOCKED"},
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
        "storage": os.environ.get(
            "ROBOT_STORAGE_MODE",
            "ephemeral-simulation" if environment == "Staging" else "persistent",
        ),
        "physical_hardware_approved": False,
        "frontend_url": url,
        "operator_url": operator_url if environment == "Production" else url,
        "render_service_id": os.environ["RENDER_SERVICE_ID"],
        "status": "PASS"
        if all(value == "PASS" for value in checks.values())
        else "FAIL"
        if "FAIL" in checks.values()
        else "BLOCKED",
    }
    if suite.get("failure"):
        result["failure"] = suite["failure"]
    if selected:
        observed = inspect_backend(environment, backend_sha)
        before = json.loads((directory / "backend-before" / "private.json").read_text())
        require(
            observed["private_context_sha256"] == before["private_context_sha256"],
            "Retained backend runtime configuration changed during release",
        )
        result["component_plan"] = selected
        result["components"] = {
            "frontend": {
                "commit": os.environ["GITHUB_SHA"],
                "deployment_id": vercel_id,
            },
            "backend": {
                "commit": backend_sha,
                "deployment_id": render["deployment_id"],
                "identity_sha256": selected["backend_identity_sha256"],
                "tested_build": selected["baseline"]["tested_build"],
                "runtime_context_preserved": True,
                "runtime_readiness": "PASS",
                "action": "retained"
                if environment == "Production"
                else "restarted-for-preview-origin",
            },
        }
    save(result, directory / "record.json")
    if environment == "Staging" and result["status"] == "PASS":
        verify_stage(
            result,
            result["candidate_commit"],
            result["source_sha256"],
            record["builds"],
        )
    require(result["status"] == "PASS", "Deployment acceptance blocked")


def selected_components(directory, environment):
    """Refresh provenance independently; a local preflight JSON is not authority."""
    directory = Path(directory)
    record = json.loads((directory / "preflight" / "record.json").read_text())
    selected = record.get("component_plan")
    if not selected:
        return None
    import components
    import evidence as e

    github = GitHub()
    sha = os.environ["GITHUB_SHA"]
    if environment == "Staging":
        actual, run = e.observed_context(github)
        e.trusted_staging_run(github, run, actual, completed=False)
        require(
            run["event"] == "workflow_dispatch"
            and record["workflow_run_id"] == run["id"]
            and record["candidate_commit"] == actual
            and record["valid_for_source_sha256"] == e.source_hash(),
            "Component staging preflight belongs to another owner run or source",
        )
    else:
        import free_gate

        require(
            not os.getenv("GITHUB_ACTIONS"),
            "Component production credentials stay outside repository Actions",
        )
        require(
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=e.ROOT, text=True
            ).strip()
            == sha
            and not subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=e.ROOT
            ),
            "Component production requires a clean exact-main checkout",
        )
        actor = json.loads(subprocess.check_output(["gh", "api", "user"], text=True))[
            "login"
        ]
        require(actor == e.OWNER, "Component retention requires the external owner")
        handoff = free_gate.verify(
            github, sha, os.environ.get("ROBOT_AUTHORIZATION_RUN", "")
        )
        qualification_run = github.run(handoff["approval"]["qualification"]["run_id"])
        qualified, _ = github.artifact(qualification_run, "free-release-qualification")
        require(
            record == qualified,
            "Production component preflight differs from its immutable authorization",
        )
    return components.verify(github, sha, selected)


def inspect_backend(environment, expected_sha, *, readiness=True):
    """Read actual live provider identity/readiness, without exposing environment values."""
    preflight(environment)
    base = "https://api.render.com/v1/services/" + os.environ["RENDER_SERVICE_ID"]
    token = os.environ["RENDER_API_KEY"]
    service = provider(base, token)
    entries = provider(base + "/env-vars?limit=100", token)
    values = {entry["envVar"]["key"]: entry["envVar"]["value"] for entry in entries}
    latest = provider(base + "/deploys?limit=1", token)
    require(latest, "Retained backend has no provider deployment")
    deployment = latest[0].get("deploy", latest[0])
    require(
        deployment.get("status") == "live"
        and deployment.get("commit", {}).get("id") == expected_sha,
        "Actual retained backend source is not its qualified baseline",
    )
    url = origin(service["serviceDetails"]["url"], ".onrender.com")
    from smoke import Simulator, wait_readiness

    if readiness:
        ready = wait_readiness(Simulator(url))
        require(
            ready.get("mode") == "simulation"
            and ready.get("physical_actuation") is False
            and ready.get("deployment_environment") == environment.lower(),
            "Retained backend runtime readiness or environment differs",
        )
    # This digest includes credentials solely to detect accidental/concurrent changes.
    # It stays in a private ephemeral file and is never uploaded/printed in a receipt.
    context = {
        "service": {
            key: service.get(key)
            for key in [
                "repo",
                "branch",
                "rootDir",
                "type",
                "autoDeploy",
                "autoDeployTrigger",
            ]
        },
        "details": service.get("serviceDetails"),
        "environment": values,
    }
    return {
        "commit": expected_sha,
        "deployment_id": deployment["id"],
        "status": "live",
        "readiness": "PASS" if readiness else "NOT TESTED",
        "private_context_sha256": digest(context),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=[
            "preflight",
            "resolve-preview",
            "bind-preview",
            "operator-origin",
            "receipt",
            "retain-backend",
            "component-preflight",
        ],
    )
    parser.add_argument("environment", choices=["Staging", "Production"])
    parser.add_argument("--directory")
    parser.add_argument("--browser-passed", action="store_true")
    args = parser.parse_args()
    if args.mode == "preflight":
        preflight(args.environment)
    elif args.mode == "resolve-preview":
        require(
            args.environment == "Staging", "Only staging may resolve a native Preview"
        )
        resolve_preview(args.directory)
    elif args.mode == "bind-preview":
        require(
            args.environment == "Staging", "Only synthetic Preview may change origin"
        )
        service = preflight(args.environment)
        url = origin(
            Path(args.directory, "frontend-url.txt").read_text().strip(), ".vercel.app"
        )
        frontend(url, args.environment)
        selected = selected_components(args.directory, args.environment)
        if selected:
            # Verify baseline source and readiness before the isolated origin write.
            inspect_backend(
                args.environment, selected["backend_commit"], readiness=False
            )
        provider(
            "https://api.render.com/v1/services/"
            + service
            + "/env-vars/ROBOT_PUBLIC_ORIGIN",
            os.environ["RENDER_API_KEY"],
            {"value": url},
        )
        if selected:
            # Saved origin changes require a purposeful baseline-source restart.
            # Capture the saved context after that sole change for post-start comparison.
            observed = inspect_backend(
                args.environment, selected["backend_commit"], readiness=False
            )
            path = Path(args.directory) / "backend-before" / "private.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(observed))
            path.chmod(0o600)
    elif args.mode == "component-preflight":
        require(
            args.environment == "Staging",
            "Pre-origin component inspection is staging-only",
        )
        selected = selected_components(args.directory, args.environment)
        if selected:
            inspect_backend(args.environment, selected["backend_commit"])
    elif args.mode == "retain-backend":
        require(args.environment == "Production", "Production-only component retention")
        selected = selected_components(args.directory, args.environment)
        require(selected, "Explicit frontend-only qualification required")
        observed = inspect_backend(args.environment, selected["backend_commit"])
        directory = Path(args.directory)
        path = directory / "backend-before" / "private.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(observed))
        path.chmod(0o600)
        (directory / "render.json").write_text(
            json.dumps(
                {
                    "service_id": os.environ["RENDER_SERVICE_ID"],
                    "deployment_id": observed["deployment_id"],
                    "commit": observed["commit"],
                    "status": "live",
                    "action": "retained",
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }
            )
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


def safe_failure_code(error):
    codes = {
        "Render repository, branch or backend root mismatch": "RENDER_LAYOUT",
        "Render native auto-deploy must be off": "RENDER_AUTO_DEPLOY",
        "Reviewed backend runtime and layout required": "RENDER_RUNTIME",
        "Render API URL binding mismatch": "RENDER_API_BINDING",
        "Isolated database required": "DATABASE_PATH",
        "Operator auth missing": "OPERATOR_AUTH",
        "Environment mismatch": "ENVIRONMENT_SCOPE",
        "Physical operation must be disabled": "PHYSICAL_DISABLED",
        "Staging storage binding mismatch": "STORAGE_MODE",
        "Configure the reviewed staging Turso database origin": "TURSO_CONFIGURATION",
        "Turso staging database identity mismatch": "TURSO_BINDING",
        "Turso runtime credential missing": "TURSO_CREDENTIAL",
        "Dedicated synthetic staging operator missing": "OPERATOR_BINDING",
        "Vercel root/repository mismatch": "VERCEL_LAYOUT",
        "Protected Preview required": "PREVIEW_PROTECTION",
        "Server-only frontend API origin must match its isolated Render target": "FRONTEND_API_BINDING",
        "Provider readback unavailable; inspect private provider logs": "PROVIDER_READBACK",
        "No ready native Git staging Preview for the exact candidate": "PREVIEW_NOT_READY",
    }
    return (
        codes.get(str(error), "CLOUD_VALIDATION")
        if isinstance(error, Rejected)
        else "CONFIGURATION_INPUT"
    )


if __name__ == "__main__":
    try:
        main()
    except (Rejected, KeyError, ValueError, OSError, TypeError) as error:
        raise SystemExit(
            "Robot cloud operation blocked: " + safe_failure_code(error)
        ) from None
