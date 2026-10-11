"""Read-only owner diagnostics; return allowlisted metadata and presence booleans."""

import json
import os
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read(origin, path, token):
    if not token:
        return {}, 0
    request = urllib.request.Request(origin + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            return json.loads(response.read(1024 * 1024)), response.status
    except urllib.error.HTTPError as error:
        return {}, error.code
    except (urllib.error.URLError, TimeoutError, ValueError):
        return {}, 0


KEYS = (
    "ROBOT_PUBLIC_ORIGIN", "ROBOT_OPERATOR_NAME", "ROBOT_OPERATOR_PASSWORD_HASH",
    "ROBOT_DATABASE_PATH", "ROBOT_ACTUATION_ENABLED", "ROBOT_DEPLOYMENT_ENVIRONMENT",
    "ROBOT_STORAGE_MODE", "ROBOT_EDGE_DEVICE_ID", "ROBOT_EDGE_TOKEN_SHA256",
)


def render(service_id):
    token = os.environ.get("RENDER_API_KEY", "")
    base = "https://api.render.com/v1/services/" + service_id
    service, status = read(base, "", token)
    entries, env_status = read(base, "/env-vars?limit=100", token)
    deployments, deploy_status = read(base, "/deploys?limit=1", token)
    values = {e.get("envVar", e).get("key"): e.get("envVar", e).get("value")
              for e in entries} if isinstance(entries, list) else {}
    latest = deployments[0].get("deploy", {}) if isinstance(deployments, list) and deployments else {}
    details = service.get("serviceDetails", {})
    return {
        "service_id": service_id, "api_http": status,
        "repository_matches": service.get("repo", "").removesuffix(".git") == "https://github.com/DruHustle/onesa-ai-robot",
        "branch_main": service.get("branch") == "main",
        "backend_root_matches": service.get("rootDir") == "onesa-ai-robot-backend",
        "native_auto_deploy_disabled": service.get("autoDeployTrigger") == "off" or service.get("autoDeploy") == "no",
        "free_plan": details.get("plan") == "free",
        "disk_present": bool(details.get("disk")),
        "environment_api_http": env_status,
        "environment_inventory_complete": env_status == 200 and isinstance(entries, list) and len(entries) < 100,
        "configured": {k: bool(values.get(k)) for k in KEYS},
        "physical_actuation_disabled": values.get("ROBOT_ACTUATION_ENABLED") == "false",
        "persistent_storage_mode": values.get("ROBOT_STORAGE_MODE") == "persistent",
        "deployments_api_http": deploy_status,
        "latest_deployment_state": latest.get("status"),
    }


def vercel():
    project_id = os.environ.get("VERCEL_PROJECT_ID", "")
    org_id = os.environ.get("VERCEL_ORG_ID", "")
    if not project_id or not org_id:
        return {"api_http": 0, "project_identifiers_configured": False}
    # IDs are encoded as URL components, never interpreted as another origin.
    from urllib.parse import quote, urlencode
    path = "/v9/projects/" + quote(project_id, safe="")
    query = "?" + urlencode({"teamId": org_id})
    token = os.environ.get("VERCEL_TOKEN", "")
    project, status = read("https://api.vercel.com", path + query, token)
    entries, env_status = read("https://api.vercel.com", path + "/env" + query, token)
    env = entries.get("envs", [])
    return {
        "api_http": status, "project_identifiers_configured": True,
        "repository_matches": project.get("link", {}).get("repo") == "onesa-ai-robot",
        "frontend_root_matches": project.get("rootDirectory") == "onesa-ai-robot-frontend",
        "preview_protection_present": bool(project.get("ssoProtection")),
        "environment_api_http": env_status,
        "production_configured": {k: any(e.get("key") == k and "production" in e.get("target", [])
                                         for e in env) for k in ["ROBOT_API_URL"]},
        "dedicated_staging_project_verified": False,
    }


def main():
    if os.environ.get("GITHUB_REPOSITORY") != "DruHustle/onesa-ai-robot":
        raise SystemExit("Owner repository required")
    print(json.dumps({"read_only": True, "source_commit": os.environ.get("GITHUB_SHA"),
                      "production": render("srv-db5k88flk1mc73aa9110"),
                      "staging": render("srv-db5k9ft9fdbs73d622cg"),
                      "frontend": vercel(), "deployment_requested": False}, indent=2))


if __name__ == "__main__":
    main()
