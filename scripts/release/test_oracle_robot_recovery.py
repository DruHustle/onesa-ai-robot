"""Real disposable signed-ledger recovery tests; never hosted acceptance."""

import copy
import datetime as dt
import hashlib
import json
import os
import subprocess
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import oracle_owner as o
import oracle_robot as r
import oracle_robot_recovery as recovery
import test_oracle_owner as fixtures


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.OwnerStoreTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.OwnerStoreTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store, self.root = self.fixture.store, self.fixture.root
        self.binding = self.fixture.binding
        old = self.binding["repository"]
        self.binding["repository"] = "DruHustle/onesa-robot"
        profile = self.store.policy["components"].pop(old + ":api")
        self.store.policy["components"][self.binding["repository"] + ":api"] = profile
        (self.root / "policy.json").write_bytes(o.canonical(self.store.policy))
        self.store.trust["policy_sha256"] = o.file_digest(self.root / "policy.json")
        (self.root / "trust.json").write_bytes(o.canonical(self.store.trust))
        self.fixture.commission_fixture()
        auth = self.fixture.authorization()
        with (
            patch.object(
                self.store,
                "inspect",
                side_effect=o.Rejected("original observer failed"),
            ),
            self.assertRaises(o.Rejected),
        ):
            self.store.deploy(auth)
        self.operation = self.store.db.execute("SELECT id FROM deployments").fetchone()[
            0
        ]
        self.intent, self.receipt = recovery.original(self.store, self.operation)
        # Historical original approvals are not renewed to inspect the same runtime.
        now = o.timestamp() + dt.timedelta(hours=2)
        self.store.clock = lambda: now
        self.pins = {"runners/observer.py": "f" * 64}
        self.source = {
            "repository": self.binding["repository"],
            "candidate_commit": "9" * 40,
            "source_tree": "8" * 40,
            "source_sha256": "7" * 64,
        }
        self.components = {
            "paths": list(recovery.COMPONENT_PATHS),
            "files": 4,
            "sha256": "6" * 64,
        }
        self.plan_path = self.root / "original-plan.json"
        self.plan = {
            "verifier_store": str(self.root),
            "bindings": {"api": self.binding},
            "probe_image": "old",
            "cli_image": "old",
            "builder_image": "old",
            "builder_sha256": "old",
        }
        self.plan_path.write_bytes(o.canonical(self.plan))
        self.plan_path.chmod(0o600)
        self.details = {
            "operation_id": self.operation,
            "purpose": "read-only-existing-robot-api-observer-correction",
            "installed_root": str(self.root),
            "file_pins": self.pins,
            "observer_source": self.source,
            "unchanged_backend_components": self.components,
            "original_plan": str(self.plan_path),
            "original_plan_sha256": o.file_digest(self.plan_path),
            "provider_requests": 0,
            "qualification_reissued": False,
            "authorization_reissued": False,
        }
        self.commission = self.store.put(
            "production-observer-commission",
            self.binding,
            self.details,
            parent=self.operation,
        )["record"]["id"]
        self.stack = self.enterContext(ExitStack())
        self.stack.enter_context(
            patch.object(recovery, "installed_files", return_value=self.pins)
        )
        self.stack.enter_context(
            patch.object(
                recovery.Observer, "current_policy", return_value={"toolchain": {}}
            )
        )
        self.stack.enter_context(
            patch.object(recovery, "unchanged_components", return_value=self.components)
        )
        private = o.private
        self.stack.enter_context(
            patch.object(
                recovery.owner,
                "private",
                side_effect=lambda p, **kw: private(p, **{"uid": os.getuid(), **kw}),
            )
        )

    def actual(self):
        return {
            "binding": self.binding,
            "environment": "production",
            "workflow_run_id": 0,
            "operation_id": self.operation,
            "deployment_id": self.receipt["details"]["observations"]["deployment_id"],
            "checks": {
                k: "PASS"
                for k in self.store.policy["components"][
                    self.binding["repository"] + ":api"
                ]["required_checks"]["production"]
            },
            "observed_at": self.store.clock().isoformat(),
        }

    def test_historical_original_chain_accepts_one_actual_observation_without_new_release(
        self,
    ):
        before = self.store.db.execute("SELECT count(*) FROM records").fetchone()[0]
        count = (self.root / "provider-count").read_text()
        with patch.object(r, "runner", return_value=self.actual()) as runner:
            result = recovery.observe(
                self.store, self.commission, self.root, "synthetic-only"
            )
            again = recovery.observe(
                self.store, self.commission, self.root, "synthetic-only"
            )
        self.assertEqual(result["record"]["kind"], "production-verification")
        self.assertEqual(again["state"], "accepted")
        self.assertEqual(runner.call_count, 1)
        self.assertEqual((self.root / "provider-count").read_text(), count)
        self.assertEqual(
            self.store.db.execute("SELECT count(*) FROM records").fetchone()[0],
            before + 1,
        )
        self.assertNotIn("synthetic-only", json.dumps(result))

    def test_wrong_observations_fail_closed_and_leave_operation_unresolved(self):
        bad = []
        for field, value in [
            ("binding", {**self.binding, "candidate_commit": "0" * 40}),
            ("environment", "staging"),
            ("workflow_run_id", 123),
            ("workflow_run_id", False),
            ("operation_id", "wrong"),
            ("deployment_id", "other"),
            ("observed_at", (self.store.clock() - dt.timedelta(minutes=6)).isoformat()),
        ]:
            bad.append({**self.actual(), field: value})
        for field, value in [
            ("component", "frontend"),
            ("target_environment", "staging"),
            ("artifact_digest", "sha256:" + "0" * 64),
            ("source_tree", "0" * 40),
            ("build_sha256", "0" * 64),
        ]:
            bad.append({**self.actual(), "binding": {**self.binding, field: value}})
        for status in ["FAIL", "SKIP", None]:
            value = self.actual()
            value["checks"][next(iter(value["checks"]))] = status
            bad.append(value)
        for value in bad:
            with (
                self.subTest(value=value),
                patch.object(r, "runner", return_value=value),
                self.assertRaises(o.Rejected),
            ):
                recovery.observe(
                    self.store, self.commission, self.root, "synthetic-only"
                )
        self.assertEqual(
            self.store.db.execute("SELECT state FROM deployments").fetchone()[0],
            "deployed-unverified",
        )
        self.assertEqual(
            self.store.db.execute(
                "SELECT count(*) FROM records WHERE kind='production-verification'"
            ).fetchone()[0],
            0,
        )

    def test_all_original_ancestors_and_authorization_attempt_must_remain_unrevoked(
        self,
    ):
        rows = self.store.db.execute("SELECT id FROM records").fetchall()
        for (identity,) in rows:
            self.store.db.execute(
                "UPDATE records SET revoked=1 WHERE id=?", (identity,)
            )
            try:
                with self.subTest(identity=identity), self.assertRaises(o.Rejected):
                    recovery.Observer(
                        self.store, self.commission, self.root, ""
                    ).validate_invocation(
                        self.binding,
                        {"operation_id": self.operation, "read_only": True},
                    )
            finally:
                self.store.db.execute(
                    "UPDATE records SET revoked=0 WHERE id=?", (identity,)
                )

    def test_readonly_completion_preserves_independent_staging_without_transferring_its_source(
        self,
    ):
        plan = {
            "schema_version": 1,
            "bindings": {"api": self.binding},
            "api_origins": {
                "staging": "https://robot-api-staging.onesa.eu",
                "production": "https://robot-api.onesa.eu",
            },
            "origins": {
                "staging": "https://fixture.example.invalid",
                "production": "https://robot.onesa.eu",
            },
            "compose_sha256": "5" * 64,
            "baseline_runtime_sha256": self.binding["configuration_sha256"],
        }
        values, pins = {}, {}
        for env in ["staging", "production"]:
            prepared, runtime = (
                Path("/fixture/prepared-" + env),
                Path("/fixture/runtime-" + env),
            )
            v = {
                "ROBOT_DEPLOYMENT_ENVIRONMENT": env,
                "ROBOT_STORAGE_MODE": "turso",
                "ROBOT_ACTUATION_ENABLED": "false",
                "ROBOT_PUBLIC_ORIGIN": plan["origins"][env],
                "ROBOT_OPERATOR_NAME": "fixture",
                "ROBOT_TURSO_DATABASE_URL": env + "-fixture-url",
                "ROBOT_TURSO_AUTH_TOKEN": env + "-fixture-bearer",
                "ROBOT_OPERATOR_PASSWORD_HASH": env + "-fixture-hash",
            }
            values[prepared], values[runtime] = dict(v), dict(v)
            pins[prepared] = pins[runtime] = self.binding["configuration_sha256"][env]
        values[Path("/fixture/runtime-staging")]["ROBOT_RELEASE_COMMIT"] = (
            "separate-reviewed-staging"
        )
        pins[Path("/fixture/runtime-staging")] = "2" * 64
        pins[r.COMPOSE] = plan["compose_sha256"]
        pins[self.root / "source.tar"] = self.binding["source_sha256"]
        pins[self.root / "image.tar.gz"] = self.binding["build_sha256"]
        observer = Mock()
        observer.original_plan.return_value = plan
        observer.security_path.return_value = self.root / "supplemental-scan.json"
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    r,
                    "ENV",
                    {
                        env: Path("/fixture/runtime-" + env)
                        for env in ["staging", "production"]
                    },
                )
            )
            stack.enter_context(
                patch.object(r, "private", side_effect=lambda p, **kw: Path(p))
            )
            stack.enter_context(
                patch.object(r, "sha", side_effect=lambda p: pins[Path(p)])
            )
            stack.enter_context(
                patch.object(
                    r, "read", side_effect=lambda p: plan if p == r.PLAN else {}
                )
            )
            stack.enter_context(
                patch.object(r, "runtime_values", side_effect=lambda p: values[Path(p)])
            )
            stack.enter_context(
                patch.object(
                    r,
                    "candidate_environment",
                    side_effect=lambda b, env: Path("/fixture/prepared-" + env),
                )
            )
            stack.enter_context(
                patch.object(r, "component_folder", return_value=self.root)
            )
            for name in [
                "verify_toolchain",
                "source_inventory",
                "image_security",
                "verify_application_bytes",
                "verify_probe_bytes",
                "credentials",
            ]:
                stack.enter_context(patch.object(r, name))
            with self.assertRaises(r.Refused):
                r.validate_plan(self.binding)
            r.validate_plan(self.binding, observer=observer)
            observer.production_credentials.assert_called_once()
            pins[Path("/fixture/runtime-production")] = "3" * 64
            with self.assertRaises(r.Refused):
                r.validate_plan(self.binding, observer=observer)
            pins[Path("/fixture/runtime-production")] = self.binding[
                "configuration_sha256"
            ]["production"]
            pins[Path("/fixture/prepared-staging")] = "4" * 64
            with self.assertRaises(r.Refused):
                r.validate_plan(self.binding, observer=observer)

    def test_external_installation_revocation_blocks_cached_store(self):
        registry = json.loads(self.fixture.anchor.read_bytes())
        registry["installations"][str(self.root)]["active"] = False
        self.fixture.anchor.write_bytes(o.canonical(registry))
        with self.assertRaises(o.Rejected), patch.object(r, "runner") as runner:
            recovery.observe(self.store, self.commission, self.root, "")
        runner.assert_not_called()

    def test_expired_or_modified_commission_cannot_run_observer(self):
        self.store.clock = lambda: o.timestamp() + dt.timedelta(days=2)
        with patch.object(r, "runner") as runner, self.assertRaises(o.Rejected):
            recovery.observe(self.store, self.commission, self.root, "")
        runner.assert_not_called()

    def test_changed_tool_source_or_non_readonly_context_refused(self):
        observer = recovery.Observer(self.store, self.commission, self.root, "")
        for context in [
            {"operation_id": self.operation, "read_only": False},
            {"operation_id": self.operation, "read_only": True, "PASS": True},
            {"operation_id": "other", "read_only": True},
        ]:
            with self.subTest(context=context), self.assertRaises(o.Rejected):
                observer.validate_invocation(self.binding, context)
        with (
            patch.object(recovery, "installed_files", return_value={}),
            self.assertRaises(o.Rejected),
        ):
            observer.record()
        with (
            patch.object(
                recovery, "unchanged_components", return_value={"changed": True}
            ),
            self.assertRaises(o.Rejected),
        ):
            observer.validate_invocation(
                self.binding, {"operation_id": self.operation, "read_only": True}
            )

    def test_password_is_hash_confirmed_and_physical_gate_stays_disabled(self):
        password = "fixture-password"
        salt = b"0123456789abcdef"
        digest = hashlib.scrypt(
            password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64
        ).hex()
        values = {
            "ROBOT_OPERATOR_NAME": "fixture",
            "ROBOT_OPERATOR_PASSWORD_HASH": f"scrypt${salt.hex()}${digest}",
            "ROBOT_ACTUATION_ENABLED": "false",
            "ROBOT_STORAGE_MODE": "turso",
        }
        observer = recovery.Observer(self.store, self.commission, self.root, password)
        with patch.object(r, "runtime_values", return_value=values):
            self.assertEqual(
                observer.production_credentials(),
                {"operator": "fixture", "password": password},
            )
            observer.password = "wrong"
            with self.assertRaises(o.Rejected):
                observer.production_credentials()
            observer.password = password
            values["ROBOT_ACTUATION_ENABLED"] = "true"
            with self.assertRaises(o.Rejected):
                observer.production_credentials()

    def test_interrupted_observation_can_resume_without_duplicate_provider_request(
        self,
    ):
        with (
            patch.object(r, "runner", side_effect=RuntimeError("interrupted")),
            self.assertRaises(RuntimeError),
        ):
            recovery.observe(self.store, self.commission, self.root, "")
        with patch.object(r, "runner", return_value=self.actual()):
            recovery.observe(self.store, self.commission, self.root, "")
        self.assertEqual((self.root / "provider-count").read_text(), "1")

    def test_simultaneous_observer_lock_refuses_second_attempt(self):
        with recovery.observation_lock(self.store):
            with (
                self.assertRaises(BlockingIOError),
                patch.object(r, "runner") as runner,
            ):
                recovery.observe(self.store, self.commission, self.root, "")
            runner.assert_not_called()

    def test_original_plan_bytes_are_preserved_and_changes_are_refused(self):
        observer = recovery.Observer(self.store, self.commission, self.root, "")
        original = self.plan_path.read_bytes()
        tool = {
            k: "new-" + k
            for k in ["probe_image", "cli_image", "builder_image", "builder_sha256"]
        }
        with patch.object(observer, "current_policy", return_value={"toolchain": tool}):
            result = observer.original_plan()
        self.assertEqual(result["bindings"], self.plan["bindings"])
        self.assertEqual(result["probe_image"], tool["probe_image"])
        self.assertEqual(self.plan_path.read_bytes(), original)
        self.plan_path.write_bytes(original + b" ")
        with self.assertRaises(o.Rejected):
            observer.original_plan()

    def test_signed_but_incomplete_original_evidence_is_refused(self):
        # A real issuer signature alone never turns incomplete observations into PASS.
        details = copy.deepcopy(self.receipt["details"])
        details["observations"]["checks"] = {}
        replacement = self.store.put(
            "deployment-receipt", self.binding, details, parent=self.operation
        )
        self.store.db.execute("DELETE FROM records WHERE id=?", (self.receipt["id"],))
        with self.assertRaises(o.Rejected):
            recovery.original(self.store, self.operation)
        self.assertTrue(replacement["signature"])

    def test_real_git_archives_preserve_only_unchanged_backend_edge_ros(self):
        repo = self.root / "synthetic-source"
        repo.mkdir(mode=0o700)

        def git(*args):
            return subprocess.check_output(
                ["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL
            )

        git("init", "-q")
        for name in [
            "onesa-ai-robot-backend/robot_api/main.py",
            "onesa-ai-robot-backend/robot_api/inspection.py",
            "edge/source.txt",
            "ros2/source.txt",
            "frontend/theme.css",
        ]:
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic bytes\n")

        def archive(target):
            git("add", ".")
            git(
                "-c",
                "user.email=fixture@example.invalid",
                "-c",
                "user.name=Fixture",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "synthetic-only",
            )
            target.write_bytes(git("archive", "--format=tar", "HEAD"))
            target.chmod(0o600)
            return {
                "candidate_commit": git("rev-parse", "HEAD").decode().strip(),
                "source_tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
                "source_sha256": o.file_digest(target),
            }

        original = archive(self.root / "source.tar")
        (repo / "frontend/theme.css").write_text("changed frontend only\n")
        current = archive(self.root / "tool-source.tar")
        installation = self.root / "installation.json"

        def metadata(source):
            installation.write_bytes(
                o.canonical(
                    {
                        "source": source["candidate_commit"],
                        "source_tree": source["source_tree"],
                    }
                )
            )
            installation.chmod(0o600)

        metadata(current)
        # Exercise the real archive parser rather than the observer fixture stand-in.
        self.stack.close()
        private = o.private
        with (
            patch.object(
                o,
                "private",
                side_effect=lambda p, **kw: private(p, **{"uid": os.getuid(), **kw}),
            ),
            patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
            patch.object(r, "component_folder", return_value=self.root),
        ):
            proof = recovery.unchanged_components(original, self.root, current)
            self.assertEqual(proof["files"], 4)
            (repo / "edge/source.txt").chmod(0o755)
            changed_mode = archive(self.root / "tool-source.tar")
            metadata(changed_mode)
            with self.assertRaises(o.Rejected):
                recovery.unchanged_components(original, self.root, changed_mode)
            (repo / "edge/source.txt").chmod(0o644)
            (repo / "edge/source.txt").write_text("changed backend dependency\n")
            changed = archive(self.root / "tool-source.tar")
            metadata(changed)
            with self.assertRaises(o.Rejected):
                recovery.unchanged_components(original, self.root, changed)
            with self.assertRaises(o.Rejected):
                recovery.unchanged_components(original, self.root, current)

    def test_reviewed_main_files_and_actual_ci_are_required_before_commission(self):
        github = Mock()
        github.qualify.return_value = [{"run_id": 123, "run_attempt": 1}]
        installed = self.root / ("robot-" + self.source["source_tree"])
        installed.mkdir(mode=0o700)
        target = installed / "runner.py"
        target.write_bytes(b"synthetic reviewed observer")
        target.chmod(0o600)
        policy = {
            "toolchain": {
                "source_commit": self.source["candidate_commit"],
                "source_tree": self.source["source_tree"],
                "source_sha256": self.source["source_sha256"],
            }
        }
        import base64

        github.api.side_effect = [
            {
                "truncated": False,
                "tree": [
                    {
                        "path": "scripts/runner.py",
                        "type": "blob",
                        "mode": "100644",
                        "sha": "a" * 40,
                    }
                ],
            },
            {
                "encoding": "base64",
                "content": base64.b64encode(target.read_bytes()).decode(),
            },
        ]
        with patch.object(
            recovery.installer, "ALLOWED", {"runner.py": "scripts/runner.py"}
        ):
            source, _pins, ci = recovery.reviewed_source(github, installed, policy)
            self.assertEqual(source, self.source)
            self.assertEqual(ci[0]["run_id"], 123)
            github.qualify.assert_called_once_with(self.source)
            github.qualify.return_value = []
            with self.assertRaises(o.Rejected):
                recovery.reviewed_source(github, installed, policy)
            github.qualify.return_value = [{"run_id": 123}]
            github.api.side_effect = [
                {
                    "truncated": False,
                    "tree": [
                        {
                            "path": "scripts/runner.py",
                            "type": "blob",
                            "mode": "100644",
                            "sha": "a" * 40,
                        }
                    ],
                },
                {
                    "encoding": "base64",
                    "content": base64.b64encode(b"different source").decode(),
                },
            ]
            with self.assertRaises(o.Rejected):
                recovery.reviewed_source(github, installed, policy)

    def test_unreviewed_owner_bootstrap_or_actions_never_commissions(self):
        for sudo, actions in [("", ""), ("ubuntu", "true")]:
            with (
                patch.object(recovery.os, "geteuid", return_value=0),
                patch.dict(os.environ, {"SUDO_USER": sudo, "GITHUB_ACTIONS": actions}),
                patch.object(recovery, "reviewed_source") as reviewed,
            ):
                with self.assertRaises(o.Rejected):
                    recovery.commission(
                        self.store, self.operation, None, self.root, self.plan_path, {}
                    )
                reviewed.assert_not_called()

    def test_normal_runner_cannot_accept_caller_observer_or_mutating_phase(self):
        with patch.object(r, "validate_plan") as validate:
            with self.assertRaises(r.Refused):
                r.runner("production", self.binding, {}, observer=object())
            with self.assertRaises(r.Refused):
                r.runner(
                    "staging",
                    self.binding,
                    {},
                    observer=recovery.Observer(
                        self.store, self.commission, self.root, ""
                    ),
                )
            validate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
