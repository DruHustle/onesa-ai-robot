"""Read/repair only the existing free simulator staging layout; never deploy."""

import hashlib
import hmac
import json
import os
import re

from cloud import provider
from evidence import REPOSITORY, Rejected, require

SERVICE = "srv-db5k9ft9fdbs73d622cg"
API = "https://onesa-ai-robot-backend-staging.onrender.com"
TURSO = "libsql://onesa-ai-robot-backendstaging-druhustle.aws-eu-west-1.turso.io"


def target(service):
    details = service.get("serviceDetails", {})
    require(
        service.get("id") == SERVICE
        and service.get("repo", "").removesuffix(".git").rstrip("/")
        == "https://github.com/" + REPOSITORY
        and service.get("type") == "web_service"
        and service.get("runtime", details.get("env", details.get("runtime")))
        == "docker"
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
    target(service)
    if repair:
        # Disable native auto deploy in the same patch as reviewed nonsecret layout changes.
        provider(
            base,
            token,
            {
                "autoDeployTrigger": "off",
                "branch": "staging",
                "rootDir": "onesa-ai-robot-backend",
                "serviceDetails": {
                    "healthCheckPath": "/api/v1/ready",
                    "envSpecificDetails": {
                        "dockerfilePath": "./Dockerfile",
                        "dockerContext": ".",
                        "dockerCommand": "",
                    },
                },
            },
            method="PATCH",
        )
        service = provider(base, token)
        target(service)
    entries = provider(base + "/env-vars?limit=100", token)
    require(
        isinstance(entries, list) and len(entries) < 100,
        "Complete staging environment inventory required",
    )
    settings = {entry["envVar"]["key"]: entry["envVar"]["value"] for entry in entries}
    details = service["serviceDetails"]
    runtime = details.get("envSpecificDetails", {})
    layout = (
        service.get("branch") == "staging"
        and service.get("rootDir") == "onesa-ai-robot-backend"
        and service.get("autoDeployTrigger") == "off"
        and details.get("healthCheckPath") == "/api/v1/ready"
        and runtime.get("dockerfilePath") == "./Dockerfile"
        and runtime.get("dockerContext") == "."
        and not runtime.get("dockerCommand")
    )
    require(not repair or layout, "Staging layout readback mismatch")
    return {
        "target_verified": True,
        "layout_verified": layout,
        "layout_changed": repair,
        "physical_actuation_disabled": settings.get("ROBOT_ACTUATION_ENABLED")
        == "false",
        "environment_matches": settings.get("ROBOT_DEPLOYMENT_ENVIRONMENT")
        == "staging",
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
