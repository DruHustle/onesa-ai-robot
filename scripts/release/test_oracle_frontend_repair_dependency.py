"""Real signed disposable prerequisite records; never deployment authority."""

import base64
import copy
import datetime as dt
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import oracle_frontend_repair_dependency as repair
import oracle_owner as owner
import oracle_robot as robot
import oracle_robot_recovery as recovery
import test_oracle_owner as owner_fixtures
import test_oracle_robot_recovery as fixtures


class FrontendRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RecoveryTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.RecoveryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store, self.root = self.fixture.store, self.fixture.root
        self.now = self.store.clock()
        self.enterContext(patch.object(robot, "now", side_effect=lambda: self.now))
        self.enterContext(patch.object(robot, "ANCHOR", self.fixture.fixture.anchor))
        private = owner.private
        self.enterContext(
            patch.object(
                robot,
                "private",
                side_effect=lambda path, **kw: (
                    private(path, **{"uid": os.getuid(), **kw}),
                    Path(path),
                )[1],
            )
        )
        real_store = owner.Store

        self.real_store = real_store
        self.binding = {
            **self.fixture.binding,
            "component": "frontend",
            **self.fixture.source,
            "build_sha256": "5" * 64,
            "artifact_digest": "sha256:" + "4" * 64,
        }
        runtime = {
            "container_id": "a" * 64,
            "image": self.fixture.binding["artifact_digest"],
            "source": self.fixture.binding["candidate_commit"],
            "started_at": "2026-01-01T00:00:00Z",
            "restart_count": 0,
            "environment_sha256": "b" * 64,
        }
        self.proof = {
            "verifier_store": str(self.root),
            "operation_id": self.fixture.operation,
            "production_binding": self.fixture.binding,
            "staging_binding": copy.deepcopy(self.fixture.binding),
            "runtimes": {
                "production": runtime,
                "staging": {**runtime, "container_id": "c" * 64},
            },
        }
        self.plan = {
            "verifier_store": str(self.root / "separate-frontend-store"),
            "independent_api": self.proof,
        }
        self.enterContext(
            patch.object(
                robot, "inventory", return_value={robot.TARGET["production"]: runtime}
            )
        )
        self.enterContext(patch.object(robot, "summary", side_effect=copy.deepcopy))
        self.folder = self.root / "artifacts"
        self.enterContext(
            patch.object(robot, "component_folder", return_value=self.folder)
        )
        failure = self.folder / "observations" / (self.fixture.operation + "-123")
        failure.mkdir(parents=True, mode=0o700)
        for name in ["browser.stderr", "webkit-390-axe.json"]:
            (failure / name).write_text("Synthetic immutable failure fixture")
            (failure / name).chmod(0o600)
        self.details = {
            "purpose": "retained-frontend-accessibility-repair-only",
            "frontend_identity": repair.frontend_identity(self.binding),
            "frontend_store": self.plan["verifier_store"],
            "observer_commission": self.fixture.commission,
            "api_runtime": runtime,
            "api_runtimes": self.proof["runtimes"],
            "api_bindings": {
                env: self.proof[env + "_binding"] for env in ["staging", "production"]
            },
            "api_production_verified": False,
            "qualification_reissued": False,
            "production_deployment_authorized": False,
            "failure": {
                "observer_commission": self.fixture.commission,
                "directory": str(failure),
                "stderr_sha256": owner.file_digest(failure / "browser.stderr"),
                "axe_sha256": owner.file_digest(failure / "webkit-390-axe.json"),
            },
        }
        self.record = self.store.put(
            repair.KIND,
            self.fixture.binding,
            self.details,
            parent=self.fixture.operation,
        )["record"]
        self.proof["recovery_commission"] = self.record["id"]

    def test_fresh_signed_prerequisite_does_not_verify_api_or_authorize_deployment(
        self,
    ):
        before = (self.root / "provider-count").read_bytes()
        self.assertEqual(repair.verify(self.plan, self.binding), self.record["id"])
        self.assertEqual(
            self.store.db.execute(
                "SELECT state FROM deployments WHERE id=?", (self.fixture.operation,)
            ).fetchone()[0],
            "deployed-unverified",
        )
        self.assertEqual(
            self.store.db.execute(
                "SELECT count(*) FROM records WHERE kind='production-verification'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual((self.root / "provider-count").read_bytes(), before)
        with self.assertRaises(owner.Rejected):
            self.store.deploy(self.record["id"])

    def test_wrong_source_artifact_component_environment_and_scope_refused(self):
        for key, value in [
            ("candidate_commit", "0" * 40),
            ("source_tree", "0" * 40),
            ("source_sha256", "0" * 64),
            ("build_sha256", "0" * 64),
            ("artifact_digest", "sha256:" + "0" * 64),
            ("component", "api"),
            ("target_environment", "staging"),
        ]:
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                repair.verify(self.plan, {**self.binding, key: value})
        with self.assertRaises(owner.Rejected):
            repair.verify(
                {**self.plan, "verifier_store": "/another-store"}, self.binding
            )

    def test_expired_modified_revoked_records_and_changed_runtime_or_evidence_refused(
        self,
    ):
        self.now += dt.timedelta(hours=2)
        with self.assertRaises(owner.Rejected):
            repair.verify(self.plan, self.binding)
        self.now -= dt.timedelta(hours=2)
        identities = [
            self.record["id"],
            self.fixture.commission,
            self.fixture.operation,
            self.fixture.intent["parent"],
        ]
        for identity in identities:
            self.store.db.execute(
                "UPDATE records SET revoked=1 WHERE id=?", (identity,)
            )
            try:
                with self.subTest(identity=identity), self.assertRaises(owner.Rejected):
                    repair.verify(self.plan, self.binding)
            finally:
                self.store.db.execute(
                    "UPDATE records SET revoked=0 WHERE id=?", (identity,)
                )
        before = self.store.db.execute(
            "SELECT envelope FROM records WHERE id=?", (self.record["id"],)
        ).fetchone()[0]
        envelope = json.loads(before)
        envelope["record"]["details"]["frontend_identity"]["artifact_digest"] = (
            "sha256:" + "0" * 64
        )
        self.store.db.execute(
            "UPDATE records SET envelope=? WHERE id=?",
            (json.dumps(envelope), self.record["id"]),
        )
        try:
            with self.assertRaises(owner.Rejected):
                repair.verify(self.plan, self.binding)
        finally:
            self.store.db.execute(
                "UPDATE records SET envelope=? WHERE id=?", (before, self.record["id"])
            )
        with (
            patch.object(
                robot,
                "inventory",
                return_value={
                    robot.TARGET["production"]: {
                        **self.proof["runtimes"]["production"],
                        "restart_count": 1,
                    }
                },
            ),
            self.assertRaises(owner.Rejected),
        ):
            repair.verify(self.plan, self.binding)
        path = (
            self.folder
            / "observations"
            / (self.fixture.operation + "-123")
            / "browser.stderr"
        )
        path.write_text("Changed synthetic failure")
        with self.assertRaises(owner.Rejected):
            repair.verify(self.plan, self.binding)

    def test_signed_actions_boolean_run_zero_or_missing_owner_provenance_are_refused(
        self,
    ):
        original = self.store.db.execute(
            "SELECT envelope FROM records WHERE id=?", (self.record["id"],)
        ).fetchone()[0]
        for change in [
            {"workflow_run_id": 123},
            {"workflow_run_id": False},
            {"owner_provenance": {}},
            {"schema_version": True},
        ]:
            envelope = json.loads(original)
            envelope["record"].update(change)
            envelope["signature"]["value"] = base64.b64encode(
                owner.signed_bytes(
                    self.root / "signing.pem",
                    self.root / "public.pem",
                    owner.canonical(envelope["record"]),
                )
            ).decode()
            self.store.db.execute(
                "UPDATE records SET envelope=? WHERE id=?",
                (owner.canonical(envelope).decode(), self.record["id"]),
            )
            try:
                with (
                    self.subTest(change=change),
                    self.assertRaises((owner.Rejected, KeyError)),
                ):
                    repair.verify(self.plan, self.binding)
            finally:
                self.store.db.execute(
                    "UPDATE records SET envelope=? WHERE id=?",
                    (original, self.record["id"]),
                )

    def test_only_independently_accepted_frontend_on_original_api_can_repair_observer(
        self,
    ):
        other = owner_fixtures.OwnerStoreTests()
        other.setUp()
        self.addCleanup(other.doCleanups)
        old = other.binding["repository"] + ":api"
        other.binding.clear()
        other.binding.update(self.binding)
        other.ci.source = self.binding["candidate_commit"]
        profile = other.store.policy["components"].pop(old)
        other.store.policy["components"][self.binding["repository"] + ":frontend"] = (
            profile
        )
        other.store.policy["toolchain"] = {
            "source_commit": self.binding["candidate_commit"]
        }
        (other.root / "policy.json").write_bytes(owner.canonical(other.store.policy))
        other.store.trust["policy_sha256"] = owner.file_digest(
            other.root / "policy.json"
        )
        (other.root / "trust.json").write_bytes(owner.canonical(other.store.trust))
        other.commission_fixture()
        real_runner = other.store.runner

        def observed(phase, binding, context):
            result = real_runner(phase, binding, context)
            if phase == "production":
                result["observations"]["actual_runtime"] = self.proof["runtimes"][
                    "production"
                ]
            return result

        with patch.object(other.store, "runner", side_effect=observed):
            authorization = other.authorization()
            result = other.store.deploy(authorization)
        operation = result["record"]["parent"]
        reference = {
            "verifier_store": "/var/lib/onesa/release-verification/robot-owner-"
            + "f" * 40,
            "operation_id": operation,
            "verification_id": result["record"]["id"],
        }

        def opened(path, github):
            self.assertEqual(str(path), reference["verifier_store"])
            return self.real_store(other.root, github, uid=os.getuid())

        with patch.object(recovery.owner, "Store", side_effect=opened):
            value = recovery.accepted_frontend(
                self.store, reference, self.fixture.binding
            )
            self.assertEqual(value["binding"], self.binding)
            self.assertEqual(value["api_runtime"], self.proof["runtimes"]["production"])
            with self.assertRaises(owner.Rejected):
                recovery.accepted_frontend(
                    self.store,
                    reference,
                    {**self.fixture.binding, "artifact_digest": "sha256:" + "0" * 64},
                )
            other.store.db.execute(
                "UPDATE deployments SET state='deployed-unverified' WHERE id=?",
                (operation,),
            )
            with self.assertRaises(owner.Rejected):
                recovery.accepted_frontend(self.store, reference, self.fixture.binding)
            other.store.db.execute(
                "UPDATE deployments SET state='accepted' WHERE id=?", (operation,)
            )
            other.store.db.execute(
                "UPDATE records SET revoked=1 WHERE id=?",
                (reference["verification_id"],),
            )
            with self.assertRaises(owner.Rejected):
                recovery.accepted_frontend(self.store, reference, self.fixture.binding)

    def test_simultaneous_issuance_records_one_prerequisite_without_provider_request(
        self,
    ):
        # A distinct source identity keeps the first fixture record immutable.
        details = {
            **self.details,
            "frontend_identity": {
                **self.details["frontend_identity"],
                "candidate_commit": "f" * 40,
            },
        }
        barrier = threading.Barrier(2)

        def issue(_):
            store = self.real_store(
                self.root, self.store.github, uid=os.getuid(), clock=lambda: self.now
            )
            try:
                barrier.wait(timeout=10)
                try:
                    return repair._record_dependency(
                        store, self.fixture.operation, self.fixture.binding, details
                    )["record"]["id"]
                except owner.Rejected:
                    return None
            finally:
                store.db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(issue, range(2)))
        self.assertEqual(sum(value is not None for value in values), 1)
        rows = self.store.db.execute(
            "SELECT envelope FROM records WHERE kind=?", (repair.KIND,)
        ).fetchall()
        matching = [
            json.loads(row[0])["record"]
            for row in rows
            if json.loads(row[0])["record"]["details"]["frontend_identity"]
            == details["frontend_identity"]
        ]
        self.assertEqual(len(matching), 1)
        self.assertFalse(matching[0]["details"]["production_deployment_authorized"])


if __name__ == "__main__":
    unittest.main()
