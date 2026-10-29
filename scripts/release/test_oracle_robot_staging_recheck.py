"""Fresh operational reads supplement, never rewrite or renew qualification."""

import copy
import datetime as dt
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import oracle_robot as r
import oracle_robot_frontend as frontend
import oracle_robot_probe as probe


class QualifiedStagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.context = "11111111-1111-4111-8111-111111111111"
        self.current = dt.datetime.now(dt.timezone.utc)
        self.binding = {"candidate_commit": "a" * 40, "component": "api"}
        self.frontend = {**self.binding, "component": "frontend"}
        self.plan = {
            "bindings": {"frontend": self.frontend},
            "builds": {"staging": {"archive_sha256": "b" * 64}},
        }
        self.original = self.root / "observations" / self.context / "receipt.json"
        self.original.parent.mkdir(parents=True)
        self.original.write_text('{"original": "signed full staging"}')
        self.before = self.original.read_bytes()
        self.qualification = {
            "kind": "qualification",
            "binding": self.binding,
            "parent": self.context,
            "issued_at": (self.current - dt.timedelta(minutes=10)).isoformat(),
            "expires_at": (self.current + dt.timedelta(minutes=40)).isoformat(),
            "details": {
                "operations": {
                    "observations": {"staging_receipt_sha256": r.sha(self.original)}
                }
            },
        }
        self.preview = self.root / "operations" / self.context / "provider-receipt.json"
        self.preview.parent.mkdir(parents=True)
        self.preview_value = {
            "binding": self.frontend,
            "environment": "staging",
            "operation_id": self.context,
            "artifact_sha256": "b" * 64,
        }
        self.preview.write_text(json.dumps(self.preview_value))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(r, "now", return_value=self.current))
        self.stack.enter_context(
            patch.object(r, "component_folder", return_value=self.root)
        )
        self.stack.enter_context(
            patch.object(
                r, "read", side_effect=lambda p: json.loads(Path(p).read_bytes())
            )
        )
        self.static = self.stack.enter_context(patch.object(frontend, "verify_static"))
        self.observer = self.stack.enter_context(patch.object(r, "probe"))
        self.observer.side_effect = lambda binding, env, operation, *a, **kw: {
            "binding": binding,
            "environment": env,
            "operation_id": operation,
            "observed_at": self.current.isoformat(),
            "status": "PASS",
            "read_only": kw["read_only"],
            "schema_compatibility": "PASS",
            "existing_records_preserved": True,
        }
        self.create = self.stack.enter_context(
            patch.object(
                frontend,
                "create",
                side_effect=AssertionError("Provider creation forbidden"),
            )
        )
        self.activate = self.stack.enter_context(
            patch.object(
                r, "activate", side_effect=AssertionError("Deployment forbidden")
            )
        )

    def call(self, qualification=None):
        return r.qualified_staging_observation(
            self.binding,
            self.plan,
            self.root,
            self.context,
            qualification or self.qualification,
        )

    def test_actual_read_only_observer_and_existing_preview_are_required(self):
        observed, operation = self.call()
        self.assertEqual(observed["status"], "PASS")
        args, kwargs = self.observer.call_args
        self.assertEqual(args[:2], (self.binding, "staging"))
        self.assertEqual(args[2], operation)
        self.assertTrue(kwargs["read_only"])
        self.assertEqual(args[4]["preview_receipt_path"], str(self.preview))
        self.static.assert_called_once()
        self.create.assert_not_called()
        self.activate.assert_not_called()
        self.assertEqual(self.original.read_bytes(), self.before)

    def test_wrong_source_kind_parent_digest_and_expiry_fail_before_observation(self):
        variants = []
        for key, value in [
            ("kind", "context"),
            ("parent", "foreign"),
            ("binding", {**self.binding, "candidate_commit": "f" * 40}),
            ("expires_at", self.current.isoformat()),
            ("issued_at", (self.current + dt.timedelta(seconds=1)).isoformat()),
        ]:
            variants.append({**self.qualification, key: value})
        wrong = copy.deepcopy(self.qualification)
        wrong["details"]["operations"]["observations"]["staging_receipt_sha256"] = (
            "f" * 64
        )
        variants.append(wrong)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(r.Refused):
                self.call(value)
        self.observer.assert_not_called()
        self.static.assert_not_called()

    def test_missing_or_changed_preview_cannot_publish_a_replacement(self):
        for key, value in [
            ("environment", "production"),
            ("operation_id", "foreign"),
            ("artifact_sha256", "f" * 64),
            ("binding", {**self.frontend, "candidate_commit": "f" * 40}),
        ]:
            self.preview.write_text(json.dumps({**self.preview_value, key: value}))
            with self.subTest(key=key), self.assertRaises(r.Refused):
                self.call()
        self.preview.unlink()
        with self.assertRaises(FileNotFoundError):
            self.call()
        self.create.assert_not_called()
        self.observer.assert_not_called()

    def test_changed_original_during_observation_is_refused(self):
        def change(*args, **kwargs):
            self.original.write_text('{"modified":true}')
            return {
                "binding": self.binding,
                "environment": "staging",
                "operation_id": args[2],
                "status": "PASS",
                "observed_at": self.current.isoformat(),
                "read_only": True,
                "schema_compatibility": "PASS",
                "existing_records_preserved": True,
            }

        self.observer.side_effect = change
        with self.assertRaisesRegex(r.Refused, "SIGNED_STAGING_RECEIPT_CHANGED"):
            self.call()

    def test_incomplete_or_failed_recheck_is_refused(self):
        for field, value in [
            ("status", "FAIL"),
            ("environment", "production"),
            ("read_only", False),
            ("schema_compatibility", "FAIL"),
            ("existing_records_preserved", False),
            ("binding", {}),
        ]:

            def wrong(
                binding, env, operation, *args, field=field, value=value, **kwargs
            ):
                observed = {
                    "binding": binding,
                    "environment": env,
                    "operation_id": operation,
                    "observed_at": self.current.isoformat(),
                    "status": "PASS",
                    "read_only": True,
                    "schema_compatibility": "PASS",
                    "existing_records_preserved": True,
                }
                observed[field] = value
                return observed

            self.observer.side_effect = wrong
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(r.Refused, "READ_ONLY_STAGING_RECHECK_FAILED"),
            ):
                self.call()

    def test_failed_observation_is_not_relabelled_as_success(self):
        self.observer.side_effect = r.Refused("ACTUAL_HOSTED_READINESS")
        with self.assertRaisesRegex(r.Refused, "ACTUAL_HOSTED_READINESS"):
            self.call()
        self.assertEqual(self.original.read_bytes(), self.before)


class InitialStagingFreshnessTests(unittest.TestCase):
    def test_initial_qualification_cannot_use_recheck_to_extend_old_staging(self):
        current = dt.datetime.now(dt.timezone.utc)
        binding = {"candidate_commit": "a" * 40}
        stage = {
            "binding": binding,
            "status": "PASS",
            "schema_compatibility": "PASS",
            "existing_records_preserved": True,
            "observed_at": (current - dt.timedelta(minutes=6)).isoformat(),
        }
        with (
            patch.object(r, "now", return_value=current),
            patch.object(r, "read", return_value=stage),
            patch.object(r, "qualified_staging_observation") as refresh,
        ):
            with self.assertRaisesRegex(r.Refused, "FRESH_STAGING_RECEIPT_REQUIRED"):
                r.operational_observations(binding, {}, Path("/synthetic"), "context")
            refresh.assert_not_called()


class ReadOnlyStagingProbeTests(unittest.TestCase):
    def request(self, environment="staging", read_only=True):
        binding = {"repository": "DruHustle/onesa-robot", "component": "api"}
        origin = (
            "https://onesa-ai-robot-git-staging-example.vercel.app"
            if environment == "staging"
            else "https://robot.onesa.eu"
        )
        return {
            "binding": binding,
            "environment": environment,
            "read_only": read_only,
            "physical_hardware_authorized": False,
            "origin": origin,
            "api_origin": "https://robot-api"
            + ("-staging" if environment == "staging" else "")
            + ".onesa.eu",
            "expected_frontend_source": "a" * 40,
            "probe_image": "sha256:" + "b" * 64,
            "cpu_limit": "1",
            "operation_id": "fixture",
            "provider": {
                "environment": environment,
                "origin": origin,
                "provider_token_included": False,
                "binding": binding,
                "provider": {"source": "a" * 40},
            },
        }

    def test_read_only_recheck_skips_mutating_simulator_but_keeps_api_and_browser(self):
        with (
            patch.object(probe, "readonly_api", return_value={}) as api,
            patch.object(probe, "browser", return_value={}) as browser,
            patch.object(
                probe,
                "staging_legacy",
                side_effect=AssertionError("Mutation forbidden"),
            ) as legacy,
        ):
            result = probe.execute(self.request())
        self.assertEqual(result["status"], "PASS")
        api.assert_called_once()
        browser.assert_called_once()
        legacy.assert_not_called()
        self.assertNotIn("existing_simulator_and_edge", result["results"])

    def test_full_initial_staging_keeps_legacy_checks_mandatory(self):
        with (
            patch.object(probe, "readonly_api", return_value={}),
            patch.object(probe, "browser", return_value={}),
            patch.object(
                probe, "staging_legacy", side_effect=r.Refused("LEGACY_FAILED")
            ) as legacy,
        ):
            with self.assertRaisesRegex(r.Refused, "LEGACY_FAILED"):
                probe.execute(self.request(read_only=False))
            legacy.assert_called_once()

    def test_production_cannot_become_mutating_and_flag_must_be_boolean(self):
        for request in [
            self.request("production", False),
            self.request(read_only=1),
            self.request(read_only="true"),
        ]:
            with self.subTest(request=request), self.assertRaises(r.Refused):
                probe.validate_request(request)


if __name__ == "__main__":
    unittest.main()
