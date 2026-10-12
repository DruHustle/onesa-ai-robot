"""Read/repair only the existing free simulator staging layout; never deploy."""

import hashlib
import hmac
import json
import os
import re
from urllib.parse import urlencode

from cloud import provider
from evidence import REPOSITORY, Rejected, require
from service_runtime import kind as service_runtime
from service_runtime import layout as runtime_layout
from service_runtime import verified as runtime_layout_verified

SERVICE = "srv-db5k9ft9fdbs73d622cg"
API = "https://onesa-ai-robot-backend-staging.onrender.com"
TURSO = "libsql://onesa-ai-robot-backendstaging-druhustle.aws-eu-west-1.turso.io"


def target(service, *, require_docker=True):
    details = service.get("serviceDetails", {})
    require(
        service.get("id") == SERVICE
        and service.get("repo", "").removesuffix(".git").rstrip("/")
        == "https://github.com/" + REPOSITORY
        and service.get("type") == "web_service"
        and (
            not require_docker
            or service.get("runtime", details.get("runtime", details.get("env")))
            == "docker"
        )
        and details.get("plan") == "free"
        and details.get("region") == "frankfurt"
        and details.get("url") == API,
        "Identified free Robot staging service required",
    )


def operator_matches(settings):
    password = os.environ.get("ROBOT_TEST_PASSWORD", "")
    stored = settings.get("ROBOT_OPERATOR_PASSWORD_HASH", "")
    try:
        algorithm, salt, digest = stored.split("$")
        if (
            algorithm != "scrypt"
            or not re.fullmatch(r"[a-f0-9]{32}", salt)
            or not re.fullmatch(r"[a-f0-9]{128}", digest)
            or not 12 <= len(password) <= 256
        ):
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def frontend_binding():
    project, team = (
        os.environ.get("VERCEL_PROJECT_ID", ""),
        os.environ.get("VERCEL_ORG_ID", ""),
    )
    if not re.fullmatch(r"prj_[A-Za-z0-9]+", project) or not re.fullmatch(
        r"(?:team|user)_[A-Za-z0-9]+", team
    ):
        return {"frontend_target_verified": False}
    base = "https://api.vercel.com/v9/projects/" + project
    query = urlencode({"teamId": team})
    token = os.environ.get("VERCEL_TOKEN", "")
    data = provider(base + "?" + query, token)
    link = data.get("link", {})
    verified = (
        link.get("org") == "DruHustle"
        and link.get("repo") == "onesa-ai-robot"
        and data.get("rootDirectory") == "onesa-ai-robot-frontend"
    )
    if not verified:
        return {"frontend_target_verified": False}
    envs = provider(base + "/env?" + query + "&decrypt=true", token)
    matching = [
        item
        for item in envs.get("envs", [])
        if item.get("key") == "ROBOT_API_URL"
        and "preview" in item.get("target", [])
        and item.get("gitBranch") == "staging"
    ]
    return {
        "frontend_target_verified": True,
        "frontend_staging_api_matches": len(matching) == 1
        and matching[0].get("value") == API,
    }


def inspect_or_repair(repair=False):
    require(
        os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
        and os.environ.get("GITHUB_ACTOR") == "DruHustle"
        and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
        and os.environ.get("GITHUB_REF")
        in (
            {"refs/heads/staging"}
            if repair
            else {"refs/heads/dev", "refs/heads/staging"}
        ),
        "Owner hosted staging operator required",
    )
    require(
        os.environ.get("RENDER_SERVICE_ID") == SERVICE,
        "Staging service binding mismatch",
    )
    token = os.environ.get("RENDER_API_KEY", "")
    base = "https://api.render.com/v1/services/" + SERVICE
    service = provider(base, token)
    if not repair:
        details = service.get("serviceDetails", {})
        print(
            json.dumps(
                {
                    "identity_readback": {
                        "service_id_matches": service.get("id") == SERVICE,
                        "repository_matches": service.get("repo", "")
                        .removesuffix(".git")
                        .rstrip("/")
                        == "https://github.com/" + REPOSITORY,
                        "web_service": service.get("type") == "web_service",
                        "docker_runtime": service.get(
                            "runtime", details.get("env", details.get("runtime"))
                        )
                        == "docker",
                        "free_plan": details.get("plan") == "free",
                        "frankfurt_region": details.get("region") == "frankfurt",
                        "api_origin_matches": details.get("url") == API,
                        "wrapped_service_response": "service" in service,
                    }
                }
            )
        )
    target(service, require_docker=False)
    entries = provider(base + "/env-vars?limit=100", token)
    require(
        isinstance(entries, list) and len(entries) < 100,
        "Complete staging environment inventory required",
    )
    settings = {entry["envVar"]["key"]: entry["envVar"]["value"] for entry in entries}
    if repair:
        require(
            runtime_layout(service) is not None, "Reviewed staging runtime required"
        )
        require(
            settings.get("ROBOT_ACTUATION_ENABLED") == "false"
            and settings.get("ROBOT_DEPLOYMENT_ENVIRONMENT") == "staging",
            "Isolated simulation staging required",
        )
        require(
            service_runtime(service) != "python"
            or settings.get("ROBOT_STORAGE_MODE") == "turso",
            "Native staging requires reviewed durable Turso journal",
        )
        # Change only this known free service's source/layout; preserve every private value.
        provider(
            base,
            token,
            {
                "autoDeployTrigger": "off",
                "branch": "staging",
                "rootDir": "onesa-ai-robot-backend",
                "serviceDetails": {
                    "healthCheckPath": "/api/v1/ready",
                    "envSpecificDetails": runtime_layout(service),
                },
            },
            method="PATCH",
        )
        service = provider(base, token)
        target(service, require_docker=False)
    details = service["serviceDetails"]
    runtime = details.get("envSpecificDetails", {})
    layout = (
        service.get("branch") == "staging"
        and service.get("rootDir") == "onesa-ai-robot-backend"
        and service.get("autoDeployTrigger") == "off"
        and details.get("healthCheckPath") == "/api/v1/ready"
        and runtime_layout_verified(service)
    )
    require(not repair or layout, "Staging layout readback mismatch")
    return {
        "target_verified": True,
        "runtime_verified": runtime_layout_verified(service),
        "runtime_kind": next(
            (
                value
                for value in [
                    service.get("runtime"),
                    service.get("env"),
                    details.get("runtime"),
                    details.get("env"),
                ]
                if value
                in {"docker", "python", "node", "ruby", "go", "rust", "elixir", "image"}
            ),
            "UNRECOGNIZED",
        ),
        "dockerfile_configured": bool(runtime.get("dockerfilePath")),
        "native_build_command_configured": bool(runtime.get("buildCommand")),
        "native_start_command_configured": bool(runtime.get("startCommand")),
        "layout_verified": layout,
        "layout_changed": repair,
        "physical_actuation_disabled": settings.get("ROBOT_ACTUATION_ENABLED")
        == "false",
        "environment_matches": settings.get("ROBOT_DEPLOYMENT_ENVIRONMENT")
        == "staging",
        "cloud_database_path_matches": settings.get("ROBOT_DATABASE_PATH")
        == "/app/storage/robot.sqlite3",
        "cloud_repository_exact_matches": service.get("repo")
        in {
            "https://github.com/" + REPOSITORY,
            "https://github.com/" + REPOSITORY + ".git",
        },
        "turso_mode_selected": settings.get("ROBOT_STORAGE_MODE") == "turso",
        "turso_database_matches": settings.get("ROBOT_TURSO_DATABASE_URL") == TURSO,
        "turso_token_configured": bool(settings.get("ROBOT_TURSO_AUTH_TOKEN")),
        "operator_name_matches": settings.get("ROBOT_OPERATOR_NAME")
        == os.environ.get("ROBOT_TEST_OPERATOR", "operator"),
        "operator_password_matches": operator_matches(settings),
        "edge_device_configured": bool(settings.get("ROBOT_EDGE_DEVICE_ID")),
        "edge_token_configured": bool(settings.get("ROBOT_EDGE_TOKEN_SHA256")),
        "production_modified": False,
        "credentials_changed": False,
        "database_modified": False,
        "deployment_requested": False,
        **frontend_binding(),
    }


if __name__ == "__main__":
    try:
        print(
            json.dumps(
                inspect_or_repair(
                    os.environ.get("STAGING_OPERATION") == "repair-staging"
                ),
                indent=2,
            )
        )
    except Rejected as error:
        codes = {
            "Owner hosted staging operator required": "OWNER_CONTEXT",
            "Staging service binding mismatch": "SERVICE_BINDING",
            "Identified free Robot staging service required": "TARGET_IDENTITY",
            "Complete staging environment inventory required": "ENV_INVENTORY",
            "Provider credential missing": "CREDENTIAL_MISSING",
            "Provider readback unavailable; inspect private provider logs": "PROVIDER_READBACK",
            "Staging layout readback mismatch": "LAYOUT_READBACK",
        }
        raise SystemExit(
            "Robot staging configuration blocked: "
            + codes.get(str(error), "PROVIDER_OR_CONFIGURATION")
        ) from None
    except (ValueError, KeyError, TypeError, OSError):
        raise SystemExit(
            "Robot staging configuration blocked; no private values logged"
        ) from None
