"""Observe the latest exact-commit cloud deployment; never repair or deploy."""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from cloud import NoRedirect, frontend, origin, provider
from evidence import (
    GitHub,
    Rejected,
    observed_context,
    require,
    save,
    source_hash,
    trusted_run,
)


def live(record, environment):
    require(
        record["candidate_commit"] == os.environ["GITHUB_SHA"], "Wrong observed commit"
    )
    require(
        record["status"] == "PASS" and record["physical_hardware_approved"] is False,
        "Unqualified receipt",
    )
    require(
        record["render_service_id"] == os.environ["RENDER_SERVICE_ID"],
        "Wrong isolated Render target",
    )
    deployment_id = frontend(record["frontend_url"], environment)
    if environment == "Production":
        require(
            frontend(record["operator_url"], environment) == deployment_id,
            "Canonical operator origin changed",
        )
    base = "https://api.render.com/v1/services/" + record["render_service_id"]
    latest = provider(base + "/deploys?limit=1", os.environ["RENDER_API_KEY"])
    require(latest, "No live deployment")
    deployment = latest[0].get("deploy", latest[0])
    require(
        deployment.get("id") == record["render_deployment_id"]
        and deployment.get("status") == "live"
        and deployment.get("commit", {}).get("id") == os.environ["GITHUB_SHA"],
        "Backend replaced/failed",
    )
    service = provider(base, os.environ["RENDER_API_KEY"])
    require(
        service.get("repo") == "https://github.com/" + record["repository"]
        and service.get("rootDir") == "onesa-ai-robot-backend",
        "Backend target changed",
    )
    backend = origin(service["serviceDetails"]["url"], ".onrender.com")
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            backend + "/api/v1/ready", timeout=45
        ) as response:
            ready = json.loads(response.read(16384))
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise Rejected("Backend readiness unavailable") from None
    require(
        ready.get("status") == "ready"
        and ready.get("mode") == "simulation"
        and ready.get("physical_actuation") is False
        and ready.get("deployment_environment") == environment.lower(),
        "Unsafe/unready backend",
    )


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["observe", "stage-live"])
    parser.add_argument("--input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.mode == "stage-live":
        with open(args.input) as input_file:
            approved = json.load(input_file)
        live(approved["staging"]["record"], "Staging")
        save({"status": "PASS", "scope": "staging-live-readiness-only"}, args.output)
        return
    github = GitHub()
    sha, run = observed_context(github)
    trusted_run(
        run, "robot-monitor.yml", sha, {"main"}, event="workflow_run", completed=False
    )
    upstream = github.run(os.environ["UPSTREAM_RUN"])
    environment = os.environ["DEPLOYMENT_ENVIRONMENT"]
    workflow = "release-staging.yml" if environment == "Staging" else "deploy.yml"
    trusted_run(upstream, workflow, sha, {"main"})
    record, artifact = github.artifact(
        upstream,
        "staging-verification" if environment == "Staging" else "production-deployment",
    )
    require(record["source_sha256"] == source_hash(), "Observed source mismatch")
    live(record, environment)
    save(
        {
            "repository": record["repository"],
            "candidate_commit": sha,
            "deployment_artifact": artifact,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "status": "PASS",
            "scope": "provider-identity-and-current-readiness-only",
            "continuous_alerts": "OWNER CONFIGURATION REQUIRED",
            "physical_hardware_approved": False,
            "automatic_repairs": 0,
        },
        args.output,
    )


if __name__ == "__main__":
    try:
        main()
    except (Rejected, KeyError, OSError, ValueError, TypeError):
        raise SystemExit(
            "Deployment monitoring blocked or failed; inspect provider logs. No repair or promotion attempted."
        ) from None
