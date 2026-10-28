"""Robot frontend-only delivery: independently derive a retained backend's provenance.

An owner selects an immutable prior authorization run, never a caller's PASS file.
New candidate CI, fresh hosted staging and a new production authorization still apply.
"""

import re
from datetime import datetime, timezone

import evidence as e

MODE = "frontend-only"
IDENTITY_PATHS = (
    "onesa-ai-robot-backend",
    "render.yaml",
    ".env.example",
    "onesa-ai-robot-frontend/contracts/openapi.json",
    "onesa-ai-robot-frontend/contracts/schema.ts",
    "onesa-ai-robot-frontend/contracts/client.ts",
    "ros2",
    "edge",
)


def identity(github, sha):
    e.require(
        re.fullmatch(r"[a-f0-9]{40}", sha or ""), "Exact component source required"
    )
    tree = github.api(f"repos/{e.REPOSITORY}/git/trees/{sha}?recursive=1")
    e.require(
        tree.get("truncated") is False and len(tree.get("tree", [])) < 5000,
        "Complete bounded component tree required",
    )
    entries = {entry["path"]: entry for entry in tree["tree"]}
    result = {}
    for path in IDENTITY_PATHS:
        entry = entries.get(path, {})
        e.require(
            entry.get("type") in {"blob", "tree"}
            and entry.get("mode") in {"100644", "100755", "040000"}
            and re.fullmatch(r"[a-f0-9]{40}", entry.get("sha", "")),
            "Backend, runtime context or contract identity missing",
        )
        result[path] = {key: entry[key] for key in ("type", "mode", "sha")}
    return result


def baseline(github, authorization_run, *, now=None):
    e.require(
        str(authorization_run).isdigit(), "Prior owner authorization run required"
    )
    authorization = github.run(authorization_run)
    sha = authorization["head_sha"]
    e.trusted_run(authorization, "free-authorization.yml", sha, {"main"})
    latest = github.runs("free-authorization.yml", sha)
    e.require(
        latest and str(latest[0]["id"]) == str(authorization_run),
        "Retained backend authorization was superseded",
    )
    approval, approval_origin = github.artifact(
        authorization, "free-production-authorization"
    )
    e.require(
        approval.get("repository") == e.REPOSITORY
        and approval.get("candidate_commit") == sha
        and approval.get("workflow_run_id") == authorization["id"]
        and approval.get("approver") == e.OWNER
        and approval.get("decision") == "approve"
        and approval.get("target_environment") == "Production"
        and approval.get("physical_hardware_authorized") is False
        and e.fresh(approval["approved_at"], now or datetime.now(timezone.utc)),
        "Retained backend needs a fresh immutable software authorization",
    )
    qualification_run = github.run(approval["qualification"]["run_id"])
    e.trusted_run(
        qualification_run,
        "free-qualification.yml",
        sha,
        {"main"},
        event=qualification_run["event"],
    )
    e.require(
        qualification_run["event"] in {"workflow_dispatch", "workflow_run"}
        and qualification_run["actor"]["login"] == e.OWNER
        and qualification_run["triggering_actor"]["login"] == e.OWNER,
        "Untrusted retained backend qualification",
    )
    qualified, qualified_origin = github.artifact(
        qualification_run, "free-release-qualification"
    )
    e.require(
        qualified_origin == approval["qualification"]
        and e.digest(qualified) == approval["evidence_sha256"]
        and qualified.get("repository") == e.REPOSITORY
        and qualified.get("candidate_commit") == sha
        and qualified.get("workflow_run_id") == qualification_run["id"]
        and qualified.get("source_sha256") == approval.get("source_sha256")
        and qualified.get("CODE_VERIFIED")
        == qualified.get("STAGING_VERIFIED")
        == "PASS"
        and qualified.get("scope") == "cloud-software-only"
        and qualified.get("physical_hardware_authorized") is False
        and not qualified.get("component_plan"),
        "Retained backend qualification differs from its authorization",
    )
    # Do not chain reuse proofs or accept an edited copy of older build/stage evidence.
    code, references = e.checked_ci(github, sha)
    e.require(code == "PASS", "Retained backend CI is no longer verified")
    builds = e.artifacts_for_ci(github, references)
    e.require(
        builds == qualified["builds"], "Retained backend build provenance changed"
    )
    stage_run = github.run(qualified["staging"]["artifact"]["run_id"])
    e.trusted_staging_run(github, stage_run, sha)
    stage, stage_origin = github.artifact(stage_run, "staging-verification")
    e.require(
        stage_origin == qualified["staging"]["artifact"]
        and stage == qualified["staging"]["record"]
        and e.verify_stage(stage, sha, qualified["source_sha256"], builds, now=now)
        == "PASS",
        "Retained backend staging proof changed",
    )
    return {
        "commit": sha,
        "authorization": approval_origin,
        "qualification": qualified_origin,
        "staging": stage_origin,
        "tested_build": next(
            b for b in builds if b["application"] == e.APPLICATION_PREFIX + "-backend"
        ),
    }


def plan(github, sha, authorization_run):
    prior = baseline(github, authorization_run)
    old = identity(github, prior["commit"])
    current = identity(github, sha)
    e.require(
        current == old,
        "Frontend-only release changes backend, runtime context or contract",
    )
    comparison = github.api(f"repos/{e.REPOSITORY}/compare/{prior['commit']}...{sha}")
    e.require(
        comparison.get("status") in {"ahead", "identical"}
        and comparison.get("behind_by") == 0,
        "Retained backend is not an ancestor of this candidate",
    )
    return {
        "schema_version": 1,
        "mode": MODE,
        "repository": e.REPOSITORY,
        "frontend_commit": sha,
        "backend_commit": prior["commit"],
        "backend_identity": current,
        "backend_identity_sha256": e.digest(current),
        "baseline": prior,
        "production_backend_action": "retain-existing-qualified-source",
        "staging_backend_action": "restart-baseline-source-for-isolated-preview-origin",
        "physical_hardware_authorized": False,
    }


def verify(github, sha, selected):
    e.require(isinstance(selected, dict), "Component release plan missing")
    derived = plan(
        github, sha, selected.get("baseline", {}).get("authorization", {}).get("run_id")
    )
    e.require(
        selected == derived,
        "Component reuse proof was altered or belongs to another candidate",
    )
    return derived
