"""Independent frontend dependency checks; synthetic targets, no provider access."""

import copy
import datetime as dt
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import oracle_owner as o
import oracle_robot as r
import oracle_robot_frontend as f
import oracle_robot_recovery as recovery
import test_oracle_owner as owner_fixture


class IndependentDependencyTests(unittest.TestCase):
    def setUp(self):
        self.operation = str(uuid4())
        self.frontend = {
            "repository": "DruHustle/onesa-robot",
            "component": "frontend",
            "candidate_commit": "a" * 40,
            "source_tree": "b" * 40,
            "source_sha256": "c" * 64,
        }
        self.proof = {
            "verifier_store": "/var/lib/onesa/release-verification/robot-owner-"
            + "d" * 40,
            "operation_id": self.operation,
            "runtimes": {},
        }
        for env, value in [("staging", "1"), ("production", "2")]:
            binding = {
                **self.frontend,
                "component": "api",
                "candidate_commit": value * 40,
                "source_tree": value * 40,
                "source_sha256": value * 64,
                "build_sha256": value * 64,
                "artifact_digest": "sha256:" + value * 64,
                "target_environment": "production",
            }
            self.proof[env + "_binding"] = binding
            self.proof["runtimes"][env] = {
                "container_id": env + "-actual-fixture",
                "source": binding["candidate_commit"],
                "image": binding["artifact_digest"],
                "started_at": "fixture-start",
                "restart_count": 0,
                "environment_sha256": value * 64,
            }
        self.plan = {
            "release_component": "frontend",
            "verifier_store": "/var/lib/onesa/release-verification/robot-owner-"
            + "f" * 40,
            "bindings": {
                "frontend": self.frontend,
                "api": self.proof["production_binding"],
            },
            "retained_api": {
                k: self.proof["runtimes"]["production"][k]
                for k in ["container_id", "source", "image"]
            },
            "independent_api": self.proof,
        }

    def call(self, plan=None, *, records=None, code_error=None, scan_error=None):
        plan = plan or self.plan
        with (
            patch.object(
                r,
                "verify_invocation",
                return_value=records
                if records is not None
                else [{"kind": "production-verification", "parent": self.operation}],
            ) as verify,
            patch.object(
                r,
                "trusted_toolchain",
                return_value={
                    "source_commit": self.frontend["candidate_commit"],
                    "source_tree": self.frontend["source_tree"],
                    "source_sha256": self.frontend["source_sha256"],
                },
            ),
            patch.object(
                recovery, "unchanged_components", side_effect=code_error
            ) as code,
            patch.object(
                r,
                "component_folder",
                side_effect=lambda b: Path("/fixture") / b["candidate_commit"],
            ),
            patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
            patch.object(r, "sha", side_effect=lambda p: p.parent.name[0] * 64),
            patch.object(
                r,
                "read",
                side_effect=lambda p: {
                    "Metadata": {"ImageID": "sha256:" + p.parent.name[0] * 64},
                    "Results": [{"Vulnerabilities": []}],
                    "ArtifactName": "synthetic-fixture",
                    "CreatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                },
            ),
            patch.object(
                r, "image_security", wraps=r.image_security, side_effect=scan_error
            ),
            patch.object(r, "verify_application_bytes") as image_bytes,
            patch.object(
                r,
                "local_identity",
                side_effect=lambda b, env, p: p["independent_api"]["runtimes"][env],
            ),
        ):
            result = f.independent_api(plan, plan["bindings"]["frontend"])
            return result, verify, code, image_bytes

    def test_original_accepted_api_is_only_a_dependency_not_frontend_authority(self):
        operation, verify, code, image_bytes = self.call()
        self.assertEqual(operation, self.operation)
        self.assertEqual(
            verify.call_args.args,
            (
                self.proof["production_binding"],
                {"operation_id": self.operation, "read_only": True},
                "production",
                {"verifier_store": self.proof["verifier_store"]},
            ),
        )
        self.assertTrue(verify.call_args.kwargs["dependency"])
        self.assertEqual(code.call_count, 2)
        self.assertEqual(image_bytes.call_count, 2)
        self.assertNotEqual(
            self.frontend["candidate_commit"],
            self.proof["production_binding"]["candidate_commit"],
        )
        self.assertNotEqual(
            self.proof["staging_binding"]["candidate_commit"],
            self.proof["production_binding"]["candidate_commit"],
        )

    def test_missing_failed_or_nonaccepted_dependency_never_substitutes_qualification(
        self,
    ):
        for records in [
            [],
            [{"kind": "qualification", "parent": self.operation}],
            [{"kind": "production-verification", "parent": str(uuid4())}],
        ]:
            with self.subTest(records=records), self.assertRaises(r.Refused):
                self.call(records=records)
        for error in [
            r.Refused("REVOKED_OR_UNACCEPTED_API"),
            r.Refused("WRONG_SIGNATURE"),
        ]:
            with (
                patch.object(r, "verify_invocation", side_effect=error),
                self.assertRaises(r.Refused),
            ):
                f.independent_api(self.plan, self.frontend)

    def test_wrong_scope_store_runtime_or_retained_source_refused(self):
        cases = []
        for key, value in [
            ("release_component", "api"),
            ("retained_api", {}),
            ("bindings", {**self.plan["bindings"], "api": {}}),
        ]:
            cases.append({**copy.deepcopy(self.plan), key: value})
        for key, value in [
            ("verifier_store", "/tmp/caller-store"),
            ("verifier_store", self.plan["verifier_store"]),
            ("operation_id", "not-uuid"),
            ("runtimes", {}),
        ]:
            value_plan = copy.deepcopy(self.plan)
            value_plan["independent_api"][key] = value
            cases.append(value_plan)
        for env in ["staging", "production"]:
            for key, value in [
                ("repository", "DruHustle/other"),
                ("component", "frontend"),
                ("target_environment", "staging"),
            ]:
                value_plan = copy.deepcopy(self.plan)
                value_plan["independent_api"][env + "_binding"][key] = value
                cases.append(value_plan)
        for value in cases:
            with (
                self.subTest(value=value),
                self.assertRaises((r.Refused, ValueError, KeyError)),
            ):
                self.call(value)

    def test_changed_backend_or_failed_image_gate_blocks_frontend(self):
        for code_error, scan_error in [
            (o.Rejected("BACKEND_CHANGED"), None),
            (None, r.Refused("STALE_OR_HIGH_OR_SECRET_SCAN")),
        ]:
            with (
                self.subTest(code=code_error),
                self.assertRaises((o.Rejected, r.Refused)),
            ):
                self.call(code_error=code_error, scan_error=scan_error)
        with (
            patch.object(
                r,
                "trusted_toolchain",
                return_value={
                    "source_commit": "0" * 40,
                    "source_tree": "0" * 40,
                    "source_sha256": "0" * 64,
                },
            ),
            patch.object(
                r,
                "verify_invocation",
                return_value=[
                    {"kind": "production-verification", "parent": self.operation}
                ],
            ),
            self.assertRaises(r.Refused),
        ):
            f.independent_api(self.plan, self.frontend)

    def test_frontend_plan_never_exposes_api_deployment_or_caller_source_override(self):
        plan = {**self.plan, "schema_version": 1}
        with (
            patch.object(r, "read", return_value=plan),
            patch.object(r, "verify_toolchain") as tool,
        ):
            with self.assertRaises(r.Refused):
                r.validate_plan(plan["bindings"]["api"])
            tool.assert_not_called()
        changed = copy.deepcopy(self.plan)
        changed["independent_api"]["staging_binding"]["artifact_digest"] = (
            "sha256:" + "0" * 64
        )
        with self.assertRaises(r.Refused):
            self.call(changed)

    def test_actual_runtime_checks_each_component_identity_and_refuses_drift(self):
        rows, prepared = {}, {}
        for env in ["staging", "production"]:
            selected = self.proof[env + "_binding"]
            values = ["SYNTHETIC=1"]
            row = {
                "Id": env + "-actual-fixture",
                "Image": selected["artifact_digest"],
                "RestartCount": 0,
                "State": {
                    "Running": True,
                    "OOMKilled": False,
                    "Health": {"Status": "healthy"},
                    "StartedAt": "fixture-start",
                },
                "Config": {
                    "Env": values,
                    "Labels": {"org.onesa.source-commit": selected["candidate_commit"]},
                },
            }
            rows[r.TARGET[env]] = row
            self.proof["runtimes"][env] = r.summary(row)
            prepared[env] = {"SYNTHETIC": "1"}
        with (
            patch.object(r, "inventory", return_value=rows),
            patch.object(r, "candidate_environment", side_effect=lambda b, env: env),
            patch.object(r, "runtime_values", side_effect=lambda p: prepared[p]),
        ):
            for env in ["staging", "production"]:
                self.assertEqual(
                    r.local_identity(self.frontend, env, self.plan),
                    self.proof["runtimes"][env],
                )
            rows[r.TARGET["staging"]]["RestartCount"] = 1
            with self.assertRaises(r.Refused):
                r.local_identity(self.frontend, "staging", self.plan)
            rows[r.TARGET["staging"]]["RestartCount"] = 0
            rows[r.TARGET["production"]]["Config"]["Labels"][
                "org.onesa.source-commit"
            ] = self.frontend["candidate_commit"]
            with self.assertRaises(r.Refused):
                r.local_identity(self.frontend, "production", self.plan)


class SignedDependencyRevocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        owner_fixture.OwnerStoreTests.setUpClass()

    def test_original_authorization_attempt_revocation_blocks_accepted_dependency(self):
        fixture = owner_fixture.OwnerStoreTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        result = fixture.store.deploy(fixture.authorization())
        operation = result["record"]["parent"]
        trust = fixture.store.trust
        registry = {"installations": {str(fixture.root): {**trust, "active": True}}}
        reader = r.read
        with (
            patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
            patch.object(
                r,
                "read",
                side_effect=lambda p: (
                    registry
                    if str(p) == "/etc/onesa/oracle-release-trust.json"
                    else reader(p)
                ),
            ),
        ):
            context = {"operation_id": operation, "read_only": True}
            plan = {"verifier_store": str(fixture.root)}
            self.assertTrue(
                r.verify_invocation(
                    fixture.binding, context, "production", plan, dependency=True
                )
            )
            attempt = fixture.store.db.execute(
                "SELECT id FROM records WHERE kind='authorization-attempt'"
            ).fetchone()[0]
            fixture.store.db.execute(
                "UPDATE records SET revoked=1 WHERE id=?", (attempt,)
            )
            with self.assertRaises(r.Refused):
                r.verify_invocation(
                    fixture.binding, context, "production", plan, dependency=True
                )


if __name__ == "__main__":
    unittest.main()
