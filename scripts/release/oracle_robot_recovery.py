"""Owner-commissioned read-only completion of an existing Robot API deployment.

Never qualify, authorize, activate or redeploy an API. The original signed chain,
product source, artifact, provider receipt and plan remain immutable. A separately
reviewed observer can correct an observation defect without relabelling approval.
Its single existing production password travels in private stdin, is checked
against the bound runtime hash, and is never written to custody or a receipt.
"""

import argparse
import base64
import copy
import datetime as dt
import fcntl
import json
import os
import re
import sys
import tarfile
from contextlib import contextmanager
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parent.parent),
    str(Path(__file__).resolve().parent),
]
import oracle_install as installer
import oracle_operator_custody as custody
import oracle_owner as owner
import oracle_robot as robot

RELEASE_ROOT = Path("/var/lib/onesa/release-verification")
COMPONENT_PATHS = ("onesa-ai-robot-backend/", "edge/", "ros2/")


def signed_unrevoked(store, identity, kind=None, binding=None):
    result = store.get(identity, kind, binding, historical=True)
    pending, visited = [result["record"]], set()
    while pending:
        record = pending.pop()
        if record["id"] in visited:
            continue
        visited.add(record["id"])
        owner.require(len(visited) <= 12, "BOUNDED_ORIGINAL_API_CHAIN_REQUIRED")
        row = store.db.execute(
            "SELECT revoked FROM records WHERE id=?", (record["id"],)
        ).fetchone()
        owner.require(row and row[0] == 0, "ORIGINAL_API_CHAIN_REVOKED")
        parents = [record["parent"]] if record["parent"] else []
        if record["kind"] == "authorization":
            parents.append(record["details"]["attempt_id"])
        pending.extend(
            store.get(parent, binding=result["record"]["binding"], historical=True)[
                "record"
            ]
            for parent in parents
        )
    return result


def original(store, operation):
    intent = signed_unrevoked(store, operation, "deployment-intent")["record"]
    binding = intent["binding"]
    owner.require(
        binding["repository"] == "DruHustle/onesa-robot"
        and binding["component"] == "api"
        and binding["target_environment"] == "production"
        and intent["details"]["provider_request_budget"] == 1
        and intent["details"]["automatic_retry"] is False,
        "EXACT_EXISTING_ROBOT_API_INTENT_REQUIRED",
    )
    authorization = store.get(
        intent["parent"], "authorization", binding, historical=True
    )["record"]
    qualification = store.get(
        authorization["parent"], "qualification", binding, historical=True
    )["record"]
    profile = owner.binding_valid(binding, store.policy)
    for phase in ["staging", "operations"]:
        observed = qualification["details"][phase]["observations"]
        owner.require(
            observed["binding"] == binding
            and type(observed["workflow_run_id"]) is int
            and observed["workflow_run_id"] == 0
            and all(
                observed["checks"].get(key) == "PASS"
                for key in profile["required_checks"][phase]
            ),
            "ORIGINAL_COMPLETE_API_QUALIFICATION_REQUIRED",
        )
    receipts = store.db.execute(
        "SELECT id FROM records WHERE kind='deployment-receipt' AND parent=?",
        (operation,),
    ).fetchall()
    owner.require(len(receipts) == 1, "GENUINE_ORIGINAL_API_PROVIDER_RECEIPT_REQUIRED")
    receipt = signed_unrevoked(store, receipts[0][0], "deployment-receipt", binding)[
        "record"
    ]
    observed = receipt["details"]["observations"]
    owner.require(
        observed["binding"] == binding
        and observed["operation_id"] == operation
        and type(observed["workflow_run_id"]) is int
        and observed["workflow_run_id"] == 0
        and observed["deployment_id"]
        and all(
            observed["checks"].get(key) == "PASS"
            for key in profile["required_checks"]["deploy"]
        ),
        "SUCCESSFUL_ORIGINAL_API_DEPLOYMENT_REQUIRED",
    )
    return intent, receipt


def installed_files(root):
    owner.private(root, directory=True)
    owner.require(
        root.parent == installer.INSTALL_PARENT,
        "EXTERNAL_INSTALLED_ROBOT_OBSERVER_REQUIRED",
    )
    pins = {}
    for local in installer.ALLOWED:
        owner.private(root / local)
        pins[local] = owner.file_digest(root / local)
    return pins


def reviewed_source(github, root, policy):
    tool = policy["toolchain"]
    source = {
        "repository": "DruHustle/onesa-robot",
        "candidate_commit": tool["source_commit"],
        "source_tree": tool["source_tree"],
        "source_sha256": tool["source_sha256"],
    }
    owner.require(
        root.name == "robot-" + source["source_tree"],
        "EXACT_REVIEWED_OBSERVER_INSTALLATION_REQUIRED",
    )
    ci = github.qualify(source)
    owner.require(ci, "CURRENT_MAIN_ROBOT_OBSERVER_CI_REQUIRED")
    tree = github.api(
        "repos/"
        + source["repository"]
        + "/git/trees/"
        + source["source_tree"]
        + "?recursive=1"
    )
    owner.require(not tree.get("truncated"), "COMPLETE_OBSERVER_SOURCE_REQUIRED")
    blobs = {row["path"]: row for row in tree["tree"] if row["type"] == "blob"}
    pins = installed_files(root)
    for local, upstream in installer.ALLOWED.items():
        blob = blobs.get(upstream)
        owner.require(
            blob and blob["mode"] == "100644", "REVIEWED_ROBOT_OBSERVER_FILE_REQUIRED"
        )
        value = github.api(
            "repos/" + source["repository"] + "/git/blobs/" + blob["sha"]
        )
        owner.require(
            value["encoding"] == "base64"
            and base64.b64decode(value["content"], validate=False)
            == (root / local).read_bytes(),
            "ROBOT_OBSERVER_DIFFERS_FROM_REVIEWED_MAIN",
        )
    return source, pins, ci


def unchanged_components(binding, root, source):
    archive = robot.component_folder(binding) / "source.tar"
    owner.private(archive)
    owner.require(
        owner.file_digest(archive) == binding["source_sha256"],
        "ORIGINAL_API_SOURCE_ARCHIVE_CHANGED",
    )
    _app, old = robot.source_inventory(archive, binding)
    current = robot.read(root / "installation.json")
    tool_archive = root / "tool-source.tar"
    owner.private(tool_archive)
    owner.require(
        current["source_tree"] == source["source_tree"]
        and current["source"] == source["candidate_commit"]
        and owner.file_digest(tool_archive) == source["source_sha256"],
        "QUALIFIED_OBSERVER_SOURCE_ARCHIVE_CHANGED",
    )
    _app, new = robot.source_inventory(tool_archive, source)

    def component_pins(path, files):
        with tarfile.open(path, "r:") as archive:
            return {
                item.name: {
                    "sha256": files[item.name],
                    "executable": bool(item.mode & 0o111),
                }
                for item in archive.getmembers()
                if item.isfile() and item.name.startswith(COMPONENT_PATHS)
            }

    before = component_pins(archive, old)
    after = component_pins(tool_archive, new)
    owner.require(
        before and before == after, "CHANGED_BACKEND_REQUIRES_FRESH_INDEPENDENT_RELEASE"
    )
    return {
        "paths": list(COMPONENT_PATHS),
        "files": len(before),
        "sha256": owner.digest(before),
    }


@contextmanager
def observation_lock(store):
    with os.fdopen(
        os.open(
            store.root / "api-observer.lock",
            os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        ),
        "w",
    ) as stream:
        owner.private(store.root / "api-observer.lock")
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def accepted_frontend(store, reference, api_binding):
    owner.require(
        isinstance(reference, dict)
        and set(reference) == {"verifier_store", "operation_id", "verification_id"}
        and re.fullmatch(
            r"/var/lib/onesa/release-verification/robot-owner-[a-f0-9]{40}",
            reference["verifier_store"],
        )
        and reference["verifier_store"] != str(store.root),
        "DIRECT_ACCEPTED_FRONTEND_REFERENCE_REQUIRED",
    )
    current = owner.Store(Path(reference["verifier_store"]), store.github)
    try:
        record = signed_unrevoked(
            current, reference["verification_id"], "production-verification"
        )["record"]
        binding = record["binding"]
        owner.require(
            binding["repository"] == api_binding["repository"]
            and binding["component"] == "frontend"
            and binding["target_environment"] == "production"
            and record["parent"] == reference["operation_id"]
            and binding["candidate_commit"]
            == current.policy["toolchain"]["source_commit"],
            "EXACT_ACCEPTED_FRONTEND_COMPONENT_REQUIRED",
        )
        state = current.db.execute(
            "SELECT state FROM deployments WHERE id=?", (record["parent"],)
        ).fetchone()
        owner.require(
            state and state[0] == "accepted",
            "FRONTEND_PRODUCTION_VERIFICATION_NOT_ACCEPTED",
        )
        profile = owner.binding_valid(binding, current.policy)
        observed = record["details"]["observations"]
        runtime = observed["actual_runtime"]
        owner.require(
            observed["binding"] == binding
            and observed["operation_id"] == record["parent"]
            and observed["environment"] == "production"
            and type(observed["workflow_run_id"]) is int
            and observed["workflow_run_id"] == 0
            and all(
                observed["checks"].get(key) == "PASS"
                for key in profile["required_checks"]["production"]
            )
            and runtime["source"] == api_binding["candidate_commit"]
            and runtime["image"] == api_binding["artifact_digest"],
            "COMPLETE_FRONTEND_ACCEPTANCE_ON_ORIGINAL_API_REQUIRED",
        )
        receipts = current.db.execute(
            "SELECT id FROM records WHERE kind='deployment-receipt' AND parent=?",
            (record["parent"],),
        ).fetchall()
        owner.require(
            len(receipts) == 1, "EXACT_ACCEPTED_FRONTEND_PROVIDER_RECEIPT_REQUIRED"
        )
        receipt = signed_unrevoked(
            current, receipts[0][0], "deployment-receipt", binding
        )["record"]
        owner.require(
            receipt["details"]["observations"]["deployment_id"]
            == observed["deployment_id"],
            "ACCEPTED_FRONTEND_PROVIDER_ID_CHANGED",
        )
        return {
            **reference,
            "binding": binding,
            "deployment_id": observed["deployment_id"],
            "api_runtime": runtime,
        }
    finally:
        current.db.close()


def commission(store, operation, current, root, plan_path, security, *, frontend=None):
    owner.require(
        os.geteuid() == 0
        and os.getenv("SUDO_USER") == "ubuntu"
        and not os.getenv("GITHUB_ACTIONS")
        and store.github.owner() == owner.OWNER,
        "EXPLICIT_EXTERNAL_ROBOT_OWNER_COMMISSION_REQUIRED",
    )
    intent, _receipt = original(store, operation)
    source, pins, ci = reviewed_source(store.github, root, current.policy)
    owner.require(
        owner.file_digest(root / "oracle_owner.py")
        == store.trust["verifier_sha256"]
        == current.trust["verifier_sha256"],
        "ORIGINAL_ISSUER_IMPLEMENTATION_MUST_REMAIN_PINNED",
    )
    owner.private(plan_path)
    raw = plan_path.read_bytes()
    plan = json.loads(raw)
    owner.require(
        plan["verifier_store"] == str(store.root)
        and plan["bindings"]["api"] == intent["binding"],
        "ORIGINAL_SOURCE_BOUND_PLAN_REQUIRED",
    )
    owner.require(
        set(security) == {"api", "probe", "cli", "builder"},
        "COMPLETE_FRESH_IMMUTABLE_IMAGE_CHECKS_REQUIRED",
    )
    tool = current.policy["toolchain"]
    for kind, item in security.items():
        owner.require(
            set(item) == {"path", "sha256"},
            "SECURITY_INPUT_REFERENCES_ONLY_NO_CALLER_PASS",
        )
        path = Path(item["path"])
        owner.require(
            path.is_relative_to(RELEASE_ROOT),
            "EXTERNAL_PRIVATE_SECURITY_EVIDENCE_REQUIRED",
        )
        owner.private(path)
        owner.require(
            owner.file_digest(path) == item["sha256"], "IMAGE_SECURITY_CUSTODY_CHANGED"
        )
        robot.image_security(
            robot.read(path),
            intent["binding"]["artifact_digest"]
            if kind == "api"
            else tool[kind + "_image"],
            "amd64" if kind == "builder" else "arm64",
        )
    components = unchanged_components(intent["binding"], root, source)
    frontend_proof = None
    if frontend is not None:
        frontend_proof = accepted_frontend(store, frontend, intent["binding"])
        owner.require(
            frontend_proof["binding"]["candidate_commit"] == source["candidate_commit"],
            "RECOVERED_FRONTEND_MUST_MATCH_REVIEWED_OBSERVER_SOURCE",
        )
    with store.transaction():
        original(store, operation)
        state = store.db.execute(
            "SELECT state FROM deployments WHERE id=?", (operation,)
        ).fetchone()
        owner.require(
            state and state[0] in {"request-recorded", "deployed-unverified"},
            "UNRESOLVED_EXISTING_API_OPERATION_REQUIRED",
        )
        return store.put(
            "production-observer-commission",
            intent["binding"],
            {
                "operation_id": operation,
                "purpose": "read-only-existing-robot-api-observer-correction",
                "observer_source": source,
                "installed_root": str(root),
                "file_pins": pins,
                "observer_store": str(current.root),
                "observer_policy_sha256": current.trust["policy_sha256"],
                "original_plan": str(plan_path),
                "original_plan_sha256": owner.file_digest(plan_path),
                "security": security,
                "unchanged_backend_components": components,
                "ci": ci,
                "provider_requests": 0,
                "qualification_reissued": False,
                "authorization_reissued": False,
                **(
                    {"accepted_frontend": frontend_proof}
                    if frontend_proof is not None
                    else {}
                ),
            },
            parent=operation,
        )


class Observer:
    def __init__(self, store, identity, root, password):
        self.store, self.identity, self.root, self.password = (
            store,
            identity,
            root,
            password,
        )

    def record(self):
        owner.private(owner.ANCHOR)
        owner.commissioned(
            json.loads(owner.ANCHOR.read_bytes()), self.store.root, self.store.trust
        )
        record = signed_unrevoked(
            self.store, self.identity, "production-observer-commission"
        )["record"]
        owner.require(
            dt.datetime.fromisoformat(record["issued_at"])
            <= self.store.clock()
            < dt.datetime.fromisoformat(record["expires_at"]),
            "FRESH_ROBOT_OBSERVER_COMMISSION_REQUIRED",
        )
        details = record["details"]
        owner.require(
            details["purpose"] == "read-only-existing-robot-api-observer-correction"
            and details["operation_id"] == record["parent"]
            and details["provider_requests"] == 0
            and details["qualification_reissued"] is False
            and details["authorization_reissued"] is False
            and details["installed_root"] == str(self.root)
            and installed_files(self.root) == details["file_pins"],
            "EXACT_UNCHANGED_READ_ONLY_OBSERVER_REQUIRED",
        )
        return record

    def validate_invocation(self, binding, context):
        record = self.record()
        intent, _receipt = original(self.store, record["parent"])
        owner.require(
            binding == record["binding"] == intent["binding"]
            and context == {"operation_id": record["parent"], "read_only": True}
            and unchanged_components(
                binding, self.root, record["details"]["observer_source"]
            )
            == record["details"]["unchanged_backend_components"],
            "OBSERVER_SOURCE_TRANSFER_OR_MUTATION_REFUSED",
        )
        self.current_policy()  # Recheck its separate external commission before/after I/O.

    def current_policy(self):
        details = self.record()["details"]
        current = owner.Store(Path(details["observer_store"]), self.store.github)
        try:
            owner.require(
                current.trust["policy_sha256"] == details["observer_policy_sha256"]
                and current.policy["toolchain"]["source_commit"]
                == details["observer_source"]["candidate_commit"]
                and current.policy["toolchain"]["source_tree"]
                == details["observer_source"]["source_tree"]
                and current.policy["toolchain"]["source_sha256"]
                == details["observer_source"]["source_sha256"],
                "OBSERVER_POLICY_CHANGED",
            )
            return copy.deepcopy(current.policy)
        finally:
            current.db.close()

    def frontend_dependency(self):
        reference = self.record()["details"].get("accepted_frontend")
        if reference is None:
            return None
        keys = {
            key: reference[key]
            for key in ["verifier_store", "operation_id", "verification_id"]
        }
        current = accepted_frontend(self.store, keys, self.record()["binding"])
        owner.require(
            current == reference, "ACCEPTED_FRONTEND_OBSERVER_REFERENCE_CHANGED"
        )
        return current

    def original_plan(self):
        record = self.record()
        path = Path(record["details"]["original_plan"])
        owner.private(path)
        owner.require(
            owner.file_digest(path) == record["details"]["original_plan_sha256"],
            "ORIGINAL_PRIVATE_PLAN_CHANGED",
        )
        plan = json.loads(path.read_bytes())
        owner.require(
            plan["bindings"]["api"] == record["binding"]
            and plan["verifier_store"] == str(self.store.root),
            "ORIGINAL_API_BINDING_CHANGED",
        )
        tool = self.current_policy()["toolchain"]
        # Only the commissioned observation runtime changes in memory. Original
        # plan bytes, API/source/configuration and provider identity stay intact.
        for key in ["probe_image", "cli_image", "builder_image", "builder_sha256"]:
            plan[key] = tool[key]
        frontend = self.frontend_dependency()
        if frontend is not None:
            plan["retained_frontend"] = {
                **plan["retained_frontend"],
                "source": frontend["binding"]["candidate_commit"],
            }
        return plan

    def security_path(self, kind):
        item = self.record()["details"]["security"][kind]
        path = Path(item["path"])
        owner.private(path)
        owner.require(
            owner.file_digest(path) == item["sha256"],
            "COMMISSIONED_IMAGE_CHECK_CHANGED",
        )
        return path

    def production_credentials(self):
        self.record()
        values = robot.runtime_values(robot.ENV["production"])
        owner.require(
            values["ROBOT_ACTUATION_ENABLED"] == "false"
            and values["ROBOT_STORAGE_MODE"] == "turso"
            and custody.matches_password(
                self.password, values["ROBOT_OPERATOR_PASSWORD_HASH"]
            ),
            "EXISTING_PRODUCTION_PASSWORD_HASH_CONFIRMATION_REQUIRED",
        )
        return {"operator": values["ROBOT_OPERATOR_NAME"], "password": self.password}


def observe(store, identity, root, password):
    observer = Observer(store, identity, root, password)
    record = observer.record()
    operation = record["parent"]
    with observation_lock(store), store.transaction():
        observer.validate_invocation(
            record["binding"], {"operation_id": operation, "read_only": True}
        )
        state = store.db.execute(
            "SELECT state FROM deployments WHERE id=?", (operation,)
        ).fetchone()
        owner.require(state, "EXISTING_API_DEPLOYMENT_REQUIRED")
        if state[0] == "accepted":
            return {
                "operation_id": operation,
                "state": "accepted",
                "provider_write": False,
                "duplicate_observation": False,
            }
        owner.require(
            state[0] in {"request-recorded", "deployed-unverified"},
            "API_OPERATION_STATE_REFUSED",
        )
        actual = robot.runner(
            "production",
            record["binding"],
            {"operation_id": operation, "read_only": True},
            observer=observer,
        )
        _intent, receipt = original(store, operation)
        profile = owner.binding_valid(record["binding"], store.policy)
        owner.require(
            actual["binding"] == record["binding"]
            and actual["environment"] == "production"
            and type(actual["workflow_run_id"]) is int
            and actual["workflow_run_id"] == 0
            and actual["operation_id"] == operation
            and actual["deployment_id"]
            == receipt["details"]["observations"]["deployment_id"]
            and all(
                actual["checks"].get(key) == "PASS"
                for key in profile["required_checks"]["production"]
            )
            and dt.timedelta()
            <= store.clock() - dt.datetime.fromisoformat(actual["observed_at"])
            < dt.timedelta(minutes=5),
            "FRESH_COMPLETE_ORIGINAL_API_PRODUCTION_REQUIRED",
        )
        observer.validate_invocation(
            record["binding"], {"operation_id": operation, "read_only": True}
        )
        result = store.put(
            "production-verification",
            record["binding"],
            {
                "observer_commission": identity,
                "observer_source": record["details"]["observer_source"],
                "observations": actual,
                "provider_request_repeated": False,
                "original_source_and_artifact_preserved": True,
            },
            parent=operation,
        )
        store.db.execute(
            "UPDATE deployments SET state='accepted' WHERE id=?", (operation,)
        )
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["commission", "observe"])
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--record", required=True)
    parser.add_argument("--observer-store", type=Path)
    parser.add_argument("--original-plan", type=Path)
    parser.add_argument("--security", type=Path)
    parser.add_argument("--frontend-store", type=Path)
    parser.add_argument("--frontend-operation")
    parser.add_argument("--frontend-verification")
    args = parser.parse_args()
    owner.require(
        os.geteuid() == 0
        and os.getenv("SUDO_USER") == "ubuntu"
        and not os.getenv("GITHUB_ACTIONS"),
        "EXTERNAL_ROBOT_OWNER_ONLY",
    )
    owner.require(
        not any(
            [args.frontend_store, args.frontend_operation, args.frontend_verification]
        )
        or args.action == "commission"
        and all(
            [args.frontend_store, args.frontend_operation, args.frontend_verification]
        ),
        "EXACT_OPTIONAL_ACCEPTED_FRONTEND_REFERENCE_REQUIRED",
    )
    raw = sys.stdin.buffer.read(131073)
    owner.require(0 < len(raw) <= 131072, "PRIVATE_OWNER_REQUEST_BOUND")
    request = json.loads(raw)
    owner.require(
        set(request)
        == (
            {"owner_token"}
            if args.action == "commission"
            else {"owner_token", "production_password"}
        ),
        "NO_CALLER_PASS_OR_AUTHORIZATION_ACCEPTED",
    )
    root = Path(__file__).resolve().parent.parent
    store = owner.Store(args.store, owner.GitHub(request["owner_token"]))
    try:
        owner.require(
            store.github.owner() == owner.OWNER, "AUTHENTICATED_EXISTING_OWNER_REQUIRED"
        )
        if args.action == "commission":
            owner.require(
                args.observer_store and args.original_plan and args.security,
                "EXPLICIT_OBSERVER_PLAN_AND_SECURITY_REFERENCES_REQUIRED",
            )
            owner.private(args.security)
            current = owner.Store(args.observer_store, store.github)
            try:
                result = commission(
                    store,
                    args.record,
                    current,
                    root,
                    args.original_plan,
                    json.loads(args.security.read_bytes()),
                    frontend=(
                        {
                            "verifier_store": str(args.frontend_store),
                            "operation_id": args.frontend_operation,
                            "verification_id": args.frontend_verification,
                        }
                        if all(
                            [
                                args.frontend_store,
                                args.frontend_operation,
                                args.frontend_verification,
                            ]
                        )
                        else None
                    ),
                )
            finally:
                current.db.close()
        else:
            owner.require(
                not any([args.observer_store, args.original_plan, args.security]),
                "SIGNED_COMMISSION_ONLY",
            )
            result = observe(store, args.record, root, request["production_password"])
        print(json.dumps(result))
    finally:
        store.db.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- never disclose private credentials/provider errors
        raise SystemExit(
            "ROBOT_EXISTING_API_OBSERVER_REFUSED_INSPECT_PRIVATE_STATE"
        ) from None
