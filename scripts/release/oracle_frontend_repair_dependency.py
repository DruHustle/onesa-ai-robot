"""Owner-commissioned frontend repair while its retained API stays unverified.

This prerequisite is not API verification, qualification or release authorization.
It only breaks a demonstrated UI-verification dependency cycle. The frontend must
still pass all fresh native, staging, operational, authorization and production
checks; the original API must subsequently pass its complete production observer.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parent.parent),
    str(Path(__file__).resolve().parent),
]
import oracle_owner as owner
import oracle_robot as robot
import oracle_robot_recovery as recovery

KIND = "frontend-repair-dependency-commission"
IDENTITY = frozenset(
    {
        "repository",
        "component",
        "candidate_commit",
        "source_tree",
        "source_sha256",
        "build_sha256",
        "artifact_digest",
        "target_environment",
    }
)


def frontend_identity(binding):
    owner.require(
        binding["repository"] == "DruHustle/onesa-robot"
        and binding["component"] == "frontend"
        and binding["target_environment"] == "production",
        "FRONTEND_REPAIR_SCOPE_ONLY",
    )
    return {key: binding[key] for key in IDENTITY}


def failed_contrast(store, commission_id, folder, operation, current):
    commissioned = recovery.signed_unrevoked(
        store, commission_id, "production-observer-commission"
    )["record"]
    owner.require(
        commissioned["parent"] == operation
        and commissioned["details"]["provider_requests"] == 0,
        "ORIGINAL_READONLY_FAILURE_PROVENANCE_REQUIRED",
    )
    old_policy = owner.Store(
        Path(commissioned["details"]["observer_store"]), store.github
    )
    try:
        owner.require(
            old_policy.policy["toolchain"]["probe_files"]
            == current.policy["toolchain"]["probe_files"],
            "FAILED_BROWSER_PRODUCER_CHANGED_REQUALIFY_REQUIRED",
        )
    finally:
        old_policy.db.close()
    binding = commissioned["binding"]
    folder = Path(folder)
    owner.private(folder, directory=True)
    owner.require(
        folder.parent == robot.component_folder(binding) / "observations"
        and re.fullmatch(re.escape(operation) + r"-[0-9]+", folder.name),
        "FIXED_ORIGINAL_API_FAILURE_DIRECTORY_REQUIRED",
    )
    stderr = folder / "browser.stderr"
    owner.private(stderr)
    observed = dt.datetime.fromtimestamp(stderr.stat().st_mtime, dt.timezone.utc)
    owner.require(
        stderr.stat().st_size <= 32768
        and dt.datetime.fromisoformat(commissioned["issued_at"])
        <= observed
        < dt.datetime.fromisoformat(commissioned["expires_at"])
        and dt.timedelta() <= store.clock() - observed < dt.timedelta(hours=24),
        "ACTUAL_CURRENT_FAILED_OBSERVATION_REQUIRED",
    )
    # This exact source location is independently pinned above. Do not turn an
    # arbitrary browser/assertion/transport failure into a repair prerequisite.
    log = stderr.read_text()
    owner.require(
        "AssertionError" in log and "oracle_robot_browser.mjs:128" in log,
        "ONLY_DEMONSTRATED_RETAINED_ACCESSIBILITY_FAILURE_ALLOWED",
    )
    path = folder / "webkit-390-axe.json"
    rows = robot.read(path)
    owner.require(
        isinstance(rows, list)
        and len(rows) == 1
        and rows[0]["id"] == "color-contrast"
        and rows[0]["impact"] == "serious"
        and rows[0]["nodes"],
        "ACTUAL_RETAINED_WEBKIT_CONTRAST_FAILURE_REQUIRED",
    )
    for engine in ["chromium", "firefox", "webkit"]:
        data = robot.read(folder / (engine + "-sign-in-transport.json"))
        owner.require(
            data["state"] == "SIGN_IN_HTTP_DIAGNOSTIC_NOT_QUALIFICATION"
            and data["omitted"] == 0
            and any(
                row
                == {"path": "/api/v1/auth/login", "method": "POST", "http_status": 200}
                for row in data["responses"]
            ),
            "GENUINE_ALL_ENGINE_EXISTING_API_AUTHENTICATION_REQUIRED",
        )
    return {
        "observer_commission": commission_id,
        "directory": str(folder),
        "stderr_sha256": owner.file_digest(stderr),
        "axe_sha256": owner.file_digest(path),
        "observed_at": observed.isoformat(),
        "failure": "retained-frontend-webkit-color-contrast",
        "nodes": len(rows[0]["nodes"]),
    }


def issue(
    store,
    observer_id,
    current,
    root,
    proposal_path,
    failure_commission,
    failure_folder,
    password,
):
    owner.require(
        os.geteuid() == 0
        and os.getenv("SUDO_USER") == "ubuntu"
        and not os.getenv("GITHUB_ACTIONS")
        and store.github.owner() == owner.OWNER,
        "EXPLICIT_EXTERNAL_OWNER_REPAIR_COMMISSION_REQUIRED",
    )
    observer = recovery.Observer(store, observer_id, root, password)
    commissioned = observer.record()
    operation = commissioned["parent"]
    intent, receipt = recovery.original(store, operation)
    source, _pins, ci = recovery.reviewed_source(store.github, root, current.policy)
    observer.validate_invocation(
        intent["binding"], {"operation_id": operation, "read_only": True}
    )
    before = robot.inventory()
    _folder, original_plan = robot.validate_plan(intent["binding"], observer=observer)
    actual = robot.local_identity(intent["binding"], "production", original_plan)
    owner.require(
        actual["container_id"] == receipt["details"]["observations"]["deployment_id"],
        "ORIGINAL_DEPLOYED_API_MUST_REMAIN_UNCHANGED",
    )
    owner.private(proposal_path)
    proposal = robot.read(proposal_path)
    owner.require(
        set(proposal)
        == {"binding", "builds", "builder_sha256", "verifier_store", "independent_api"}
        and proposal["verifier_store"] == str(current.root),
        "SOURCE_BUILD_PROPOSAL_ONLY_NO_CALLER_APPROVAL",
    )
    binding = proposal["binding"]
    identity = frontend_identity(binding)
    owner.binding_valid(binding, current.policy)
    owner.require(
        all(
            binding[key] == source[key]
            for key in [
                "repository",
                "candidate_commit",
                "source_tree",
                "source_sha256",
            ]
        ),
        "EXACT_MAIN_REPAIR_FRONTEND_REQUIRED",
    )
    frontend_folder = robot.component_folder(binding)
    owner.require(
        owner.file_digest(frontend_folder / "source.tar") == binding["source_sha256"],
        "REPAIR_FRONTEND_SOURCE_ARCHIVE_CHANGED",
    )
    robot.source_inventory(frontend_folder / "source.tar", binding)
    robot.validate_frontend_builds(frontend_folder, binding, proposal)
    equivalent = recovery.unchanged_components(intent["binding"], root, source)
    proof = proposal["independent_api"]
    owner.require(
        set(proof)
        == {
            "verifier_store",
            "operation_id",
            "production_binding",
            "staging_binding",
            "runtimes",
        }
        and proof["verifier_store"] == str(store.root)
        and proof["operation_id"] == operation
        and proof["production_binding"] == intent["binding"]
        and proof["runtimes"]["production"] == actual,
        "ORIGINAL_API_AND_BOUND_TECHNICAL_STAGE_REQUIRED",
    )
    security = {}
    for environment in ["staging", "production"]:
        selected = proof[environment + "_binding"]
        row = robot.inventory()[robot.TARGET[environment]]
        owner.require(
            robot.healthy(row)
            and robot.summary(row) == proof["runtimes"][environment]
            and selected["repository"] == binding["repository"]
            and selected["component"] == "api"
            and selected["artifact_digest"] == row["Image"]
            and selected["candidate_commit"]
            == row["Config"]["Labels"].get("org.onesa.source-commit"),
            "BOUND_HEALTHY_TECHNICAL_API_DEPENDENCY_REQUIRED",
        )
        recovery.unchanged_components(selected, root, source)
        robot.verify_application_bytes(robot.component_folder(selected), selected)
        path = (
            observer.security_path("api")
            if environment == "production"
            else robot.component_folder(selected) / "scan.json"
        )
        owner.private(path)
        robot.image_security(robot.read(path), selected["artifact_digest"])
        security[environment] = {"path": str(path), "sha256": owner.file_digest(path)}
    failure = failed_contrast(
        store, failure_commission, failure_folder, operation, current
    )
    robot.unchanged(before, robot.inventory())
    details = {
        "purpose": "retained-frontend-accessibility-repair-only",
        "frontend_identity": identity,
        "frontend_store": str(current.root),
        "observer_commission": observer_id,
        "api_runtime": actual,
        "api_bindings": {
            env: proof[env + "_binding"] for env in ["staging", "production"]
        },
        "api_runtimes": proof["runtimes"],
        "api_security": security,
        "unchanged_backend_components": equivalent,
        "failure": failure,
        "ci": ci,
        "api_production_verified": False,
        "qualification_reissued": False,
        "production_deployment_authorized": False,
    }
    return _record_dependency(store, operation, intent["binding"], details)


def _record_dependency(store, operation, api_binding, details):
    identity = details["frontend_identity"]
    with store.transaction():
        recovery.original(store, operation)
        state = store.db.execute(
            "SELECT state FROM deployments WHERE id=?", (operation,)
        ).fetchone()
        owner.require(
            state and state[0] == "deployed-unverified",
            "REPAIR_REQUIRES_ORIGINAL_UNRESOLVED_API_NOT_NEW_DEPLOYMENT",
        )
        prior = store.db.execute(
            "SELECT envelope FROM records WHERE kind=? AND parent=?", (KIND, operation)
        ).fetchall()
        owner.require(
            not any(
                json.loads(row[0])["record"]["details"]["frontend_identity"] == identity
                for row in prior
            ),
            "REPAIR_PREREQUISITE_ALREADY_ISSUED_INSPECT_ONLY",
        )
        return store.put(KIND, api_binding, details, parent=operation, ttl=3600)


def current_record(plan):
    proof = plan["independent_api"]
    try:
        records = robot.verify_invocation(
            proof["production_binding"],
            {"operation_id": proof["operation_id"], "read_only": True},
            "production",
            {"verifier_store": proof["verifier_store"]},
            repair_dependency=proof["recovery_commission"],
        )
    except robot.Refused:
        raise owner.Rejected("SIGNED_REPAIR_DEPENDENCY_CHAIN_REFUSED") from None
    return next(
        record for record in records if record["id"] == proof["recovery_commission"]
    )


def verify(plan, frontend_binding):
    proof = plan["independent_api"]
    record = current_record(plan)
    details = record["details"]
    owner.require(
        record["parent"] == proof["operation_id"]
        and details["purpose"] == "retained-frontend-accessibility-repair-only"
        and details["frontend_identity"] == frontend_identity(frontend_binding)
        and details["frontend_store"] == plan["verifier_store"]
        and details["api_runtime"] == proof["runtimes"]["production"]
        and details["api_runtimes"] == proof["runtimes"]
        and details["api_bindings"]
        == {env: proof[env + "_binding"] for env in ["staging", "production"]}
        and details["api_production_verified"] is False
        and details["qualification_reissued"] is False
        and details["production_deployment_authorized"] is False,
        "EXACT_FRESH_FRONTEND_REPAIR_PREREQUISITE_REQUIRED",
    )
    failure = details["failure"]
    directory = Path(failure["directory"])
    owner.require(
        directory.parent
        == robot.component_folder(proof["production_binding"]) / "observations",
        "ORIGINAL_REPAIR_FAILURE_CUSTODY_REQUIRED",
    )
    for name, key in [
        ("browser.stderr", "stderr_sha256"),
        ("webkit-390-axe.json", "axe_sha256"),
    ]:
        path = directory / name
        owner.private(path)
        owner.require(
            owner.file_digest(path) == failure[key],
            "ORIGINAL_REPAIR_FAILURE_EVIDENCE_CHANGED",
        )
    actual = robot.summary(robot.inventory()[robot.TARGET["production"]])
    owner.require(
        actual == details["api_runtime"], "REPAIR_DEPENDENCY_API_RUNTIME_CHANGED"
    )
    return record["id"]


def security_path(plan, frontend_binding, environment):
    owner.require(
        environment in {"staging", "production"},
        "REPAIR_IMAGE_CHECK_ENVIRONMENT_REQUIRED",
    )
    verify(plan, frontend_binding)
    item = current_record(plan)["details"]["api_security"][environment]
    path = Path(item["path"])
    owner.private(path)
    owner.require(
        path.is_relative_to(recovery.RELEASE_ROOT)
        and owner.file_digest(path) == item["sha256"],
        "COMMISSIONED_DEPENDENCY_IMAGE_CHECK_CHANGED",
    )
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["store", "observer-store", "proposal", "failure-folder"]:
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ["observer-record", "failure-commission"]:
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    raw = sys.stdin.buffer.read(131073)
    owner.require(0 < len(raw) <= 131072, "PRIVATE_REPAIR_REQUEST_BOUND")
    request = json.loads(raw)
    owner.require(
        set(request) == {"owner_token", "production_password"},
        "NO_CALLER_PASS_OR_AUTHORIZATION_ACCEPTED",
    )
    store = owner.Store(args.store, owner.GitHub(request["owner_token"]))
    current = owner.Store(args.observer_store, store.github)
    try:
        result = issue(
            store,
            args.observer_record,
            current,
            Path(__file__).resolve().parent.parent,
            args.proposal,
            args.failure_commission,
            args.failure_folder,
            request["production_password"],
        )
        print(json.dumps(result))
    finally:
        current.db.close()
        store.db.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- never disclose provider credentials or private logs
        raise SystemExit(
            "FRONTEND_REPAIR_PREREQUISITE_REFUSED_INSPECT_WITHOUT_DEPLOYMENT"
        ) from None
