"""Disposable signed-store, provenance and capacity boundary tests; no live acceptance."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import oracle_owner as o
import oracle_robot as r
import oracle_robot_frontend as frontend_runner
import oracle_robot_probe as probe
import test_oracle_owner as owner_fixture


class LedgerBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        owner_fixture.OwnerStoreTests.setUpClass()

    def setUp(self):
        self.fixture = owner_fixture.OwnerStoreTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store = self.fixture.store
        self.binding = self.fixture.binding
        self.root = self.fixture.root
        trust = json.loads((self.root / "trust.json").read_bytes())
        self.registry = {"installations": {str(self.root): {**trust, "active": True}}}
        self.private = patch.object(r, "private", side_effect=lambda p, **kw: Path(p))
        self.private.start()
        self.addCleanup(self.private.stop)
        self.reader = patch.object(
            r,
            "read",
            side_effect=lambda p: (
                self.registry
                if str(p) == "/etc/onesa/oracle-release-trust.json"
                else json.loads(Path(p).read_bytes())
            ),
        )
        self.reader.start()
        self.addCleanup(self.reader.stop)

    def call(self, identifier, *, phase="staging", binding=None):
        return r.verify_invocation(
            binding or self.binding,
            {"context_id": identifier},
            phase,
            {"verifier_store": str(self.root)},
        )

    def test_valid_signed_owner_context_must_already_be_reserved(self):
        identifier = self.fixture.context()
        with self.assertRaises(r.Refused):
            self.call(identifier)
        self.store.db.execute(
            "UPDATE contexts SET state='reserved' WHERE id=?", (identifier,)
        )
        rows = self.call(identifier)
        self.assertEqual(rows[0]["id"], identifier)
        self.store.db.execute(
            "UPDATE contexts SET state='consumed' WHERE id=?", (identifier,)
        )
        with self.assertRaises(r.Refused):
            self.call(identifier)

    def test_owner_zero_is_not_unsigned_actions_or_changed_source_authority(self):
        identifier = self.fixture.context()
        self.store.db.execute(
            "UPDATE contexts SET state='reserved' WHERE id=?", (identifier,)
        )
        for key, value in [
            ("candidate_commit", "f" * 40),
            ("component", "frontend"),
            ("target_environment", "staging"),
            ("artifact_digest", "sha256:" + "f" * 64),
        ]:
            with self.subTest(key=key), self.assertRaises(r.Refused):
                self.call(identifier, binding={**self.binding, key: value})
        envelope = self.store.get(identifier)
        envelope["record"]["workflow_run_id"] = 123
        self.store.db.execute(
            "UPDATE records SET envelope=? WHERE id=?",
            (o.canonical(envelope).decode(), identifier),
        )
        with self.assertRaises(r.Refused):
            self.call(identifier)

    def test_revoked_anchor_and_revoked_record_fail_closed(self):
        identifier = self.fixture.context()
        self.store.db.execute(
            "UPDATE contexts SET state='reserved' WHERE id=?", (identifier,)
        )
        self.registry["installations"][str(self.root)]["active"] = False
        with self.assertRaises(r.Refused):
            self.call(identifier)
        self.registry["installations"][str(self.root)]["active"] = True
        self.store.db.execute("UPDATE records SET revoked=1 WHERE id=?", (identifier,))
        with self.assertRaises(r.Refused):
            self.call(identifier)

    def test_context_cannot_be_presented_as_deployment_authorization(self):
        identifier = self.fixture.context()
        self.store.db.execute(
            "UPDATE contexts SET state='reserved' WHERE id=?", (identifier,)
        )
        with self.assertRaises(r.Refused):
            self.call(identifier, phase="deploy")


class ImageEvidenceTests(unittest.TestCase):
    def test_current_exact_image_keeps_same_high_critical_and_secret_gate(self):
        scan = {
            "Metadata": {"ImageID": "fixture"},
            "Results": [{"Vulnerabilities": [{"Severity": "LOW"}]}],
            "ArtifactName": "fixture",
            "CreatedAt": r.now().isoformat(),
        }
        r.image_security(scan, "fixture")
        for changed in [
            dict(scan, Metadata={"ImageID": "wrong"}),
            dict(scan, CreatedAt="2020-01-01T00:00:00Z"),
            dict(scan, Results=[]),
            dict(scan, Results=[{"Vulnerabilities": [{"Severity": "HIGH"}]}]),
            dict(scan, Results=[{"Secrets": [{"RuleID": "synthetic"}]}]),
        ]:
            with self.subTest(changed=changed), self.assertRaises(r.Refused):
                r.image_security(changed, "fixture")


class OciDescriptorTests(unittest.TestCase):
    def proof(self, value):
        raw = json.dumps(value).encode()
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        return digest, {digest: r.base64.b64encode(raw).decode()}

    def test_scanner_config_is_cryptographically_linked_to_actual_manifest(self):
        config = "sha256:" + "a" * 64
        manifest, proof = self.proof(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": config},
            }
        )
        self.assertEqual(r.scanned_configuration_digest(manifest, proof), config)
        index, parent = self.proof(
            {
                "schemaVersion": 2,
                "manifests": [
                    {
                        "digest": manifest,
                        "platform": {"os": "linux", "architecture": "arm64"},
                    }
                ],
            }
        )
        self.assertEqual(
            r.scanned_configuration_digest(index, {**proof, **parent}), config
        )
        scan = {
            "Metadata": {"ImageID": config},
            "CreatedAt": r.now().isoformat(),
            "ArtifactName": "fixture",
            "Results": [{}],
        }
        with patch.object(r, "read", return_value=proof):
            r.image_security(scan, manifest)
            with self.assertRaises(r.Refused):
                r.image_security(
                    {**scan, "Metadata": {"ImageID": "sha256:" + "b" * 64}}, manifest
                )

    def test_modified_or_foreign_platform_proof_cannot_relabel_a_scan(self):
        digest, proof = self.proof(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": "sha256:" + "a" * 64},
            }
        )
        with self.assertRaises(r.Refused):
            r.scanned_configuration_digest(
                digest, {digest: r.base64.b64encode(b"{}").decode()}
            )
        index, parent = self.proof(
            {
                "schemaVersion": 2,
                "manifests": [
                    {
                        "digest": digest,
                        "platform": {"os": "linux", "architecture": "amd64"},
                    }
                ],
            }
        )
        with self.assertRaises(r.Refused):
            r.scanned_configuration_digest(index, {**parent, **proof})
        self.assertEqual(
            r.scanned_configuration_digest(index, {**parent, **proof}, "amd64"),
            "sha256:" + "a" * 64,
        )
        with self.assertRaises(r.Refused):
            r.scanned_configuration_digest(index, {**parent, **proof}, "ppc64")
        with self.assertRaises(r.Refused):
            r.scanned_configuration_digest(digest, {})


class ProbeCapacityTests(unittest.TestCase):
    def test_probe_fits_existing_one_cpu_daemon_without_expanding_two_cpu_ceiling(self):
        for observed, expected in [(b"1\n", "1"), (b"2\n", "2"), (b"8\n", "2")]:
            with (
                self.subTest(observed=observed),
                patch.object(r, "docker", return_value=observed) as docker,
            ):
                self.assertEqual(r.probe_cpu_limit(), expected)
                docker.assert_called_once_with(
                    "info", "--format", "{{.NCPU}}", timeout=15
                )

    def test_missing_invalid_or_failed_daemon_observation_never_defaults_to_capacity(
        self,
    ):
        for observed in [b"", b"0", b"-1", b"1.5", b"unknown", b"10000"]:
            with (
                self.subTest(observed=observed),
                patch.object(r, "docker", return_value=observed),
                self.assertRaises(r.Refused),
            ):
                r.probe_cpu_limit()
        with (
            patch.object(r, "docker", side_effect=r.Refused("DAEMON_UNAVAILABLE")),
            self.assertRaises(r.Refused),
        ):
            r.probe_cpu_limit()


class PreservationTests(unittest.TestCase):
    def test_all_existing_history_must_survive_even_outside_recent_ui_window(self):
        before = {str(i): "digest-" + str(i) for i in range(130)}
        r.preserved(before, {**before, "new-owned-fixture": "new"})
        for changed in [
            {k: v for k, v in before.items() if k != "0"},
            {**before, "0": "modified"},
        ]:
            with self.assertRaises(r.Refused):
                r.preserved(before, changed)

    def test_unrelated_container_identity_or_restart_change_refuses_acceptance(self):
        row = {
            "Id": "old",
            "Image": "same",
            "RestartCount": 0,
            "State": {"StartedAt": "same"},
            "Config": {"Env": ["SYNTHETIC=1"], "Labels": {}},
        }
        r.unchanged({"other": row}, {"other": row})
        for after in [
            {},
            {"other": {**row, "RestartCount": 1}},
            {"other": {**row, "Id": "new"}},
        ]:
            with self.assertRaises(r.Refused):
                r.unchanged({"other": row}, after)


class ProviderInterruptionTests(unittest.TestCase):
    def test_recorded_uncertain_request_cannot_be_submitted_again(self):
        import subprocess
        import tempfile
        from uuid import uuid4

        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "operations").mkdir()
            runtime = folder / "runtime.env"
            runtime.write_text("SYNTHETIC=1\n")
            mapping = folder / "images.env"
            mapping.write_text(
                "ORACLE_PRODUCTION_IMAGE=old-image\nORACLE_PRODUCTION_COMMIT=old-source\n"
            )
            row = {
                "Id": "old-id",
                "Image": "old-image",
                "RestartCount": 0,
                "State": {
                    "StartedAt": "same",
                    "Running": True,
                    "OOMKilled": False,
                    "Health": {"Status": "healthy"},
                },
                "Config": {
                    "Env": ["SYNTHETIC=1"],
                    "Labels": {"org.onesa.source-commit": "old-source"},
                },
            }
            binding = {
                "component": "api",
                "candidate_commit": "a" * 40,
                "artifact_digest": "sha256:" + "b" * 64,
            }
            plan = {
                "baseline": {"production": r.summary(row)},
                "history_baseline": {"production": {"old": "hash"}},
                "baseline_runtime_sha256": {"production": r.sha(runtime)},
            }
            operation = str(uuid4())
            calls = []

            def provider(*args, **kwargs):
                calls.append(args)
                raise subprocess.TimeoutExpired("owned-synthetic-provider", 1)

            with (
                patch.object(r, "ROOT", folder),
                patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
                patch.object(r, "IMAGES", mapping),
                patch.object(r, "ENV", {"production": runtime}),
                patch.object(r, "candidate_environment", return_value=runtime),
                patch.object(r, "authenticated_state"),
                patch.object(r, "history", return_value={"old": "hash"}),
                patch.object(
                    r, "inventory", return_value={r.TARGET["production"]: row}
                ),
                patch.object(r.subprocess, "run", side_effect=provider),
            ):
                with self.assertRaises(r.Refused):
                    r.activate(binding, "production", operation, folder, plan)
                with self.assertRaises((FileExistsError, r.Refused)):
                    r.activate(binding, "production", operation, folder, plan)
            self.assertEqual(len(calls), 1)
            receipt = json.loads(
                (
                    folder / "operations" / operation / "provider-receipt.json"
                ).read_bytes()
            )
            self.assertIsNone(receipt["provider_exit"])
            self.assertEqual(receipt["deployment_id"], "old-id")
            self.assertTrue(
                (folder / "operations" / operation / "intent.json").is_file()
            )

    def test_simultaneous_processes_share_a_nonblocking_owner_lock(self):
        import subprocess
        import sys
        import tempfile

        with tempfile.TemporaryDirectory(
            dir="/private/tmp" if Path("/private/tmp").exists() else None
        ) as temporary:
            root = Path(temporary).resolve()
            root.chmod(0o700)
            module = Path(r.__file__).resolve().parent
            code = "import sys,time;sys.path.insert(0,sys.argv[1]);import oracle_robot as r;from pathlib import Path;r.ROOT=Path(sys.argv[2]);r.private=lambda p,**kw:Path(p)\nwith r.provider_lock():\n print('LOCKED',flush=True);time.sleep(3)"
            process = subprocess.Popen(
                [sys.executable, "-c", code, str(module), str(root)],
                stdout=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(process.stdout.readline().strip(), "LOCKED")
                with (
                    patch.object(r, "ROOT", root),
                    patch.object(r, "private", side_effect=lambda p, **kw: Path(p)),
                    self.assertRaises(r.Refused),
                    r.provider_lock(),
                ):
                    self.fail("Concurrent lock must not enter")
            finally:
                process.wait(timeout=5)
                process.stdout.close()


class BrowserCredentialCleanupTests(unittest.TestCase):
    def test_timeout_removes_only_the_owned_temporary_request(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            marker = output / "preserved.json"
            marker.write_text('{"observed": true}')
            request = {
                "output": directory,
                "binding": {},
                "environment": "staging",
                "origin": "https://fixture.invalid",
                "credentials": {"password": "synthetic-test-only"},
                "provider": {},
                "read_only": False,
                "cpu_limit": "1",
                "probe_image": "sha256:" + "a" * 64,
            }
            with (
                patch.object(
                    probe.subprocess,
                    "run",
                    side_effect=subprocess.TimeoutExpired("owned-probe", 1500),
                ),
                self.assertRaises(subprocess.TimeoutExpired),
            ):
                probe.browser(request)
            self.assertFalse((output / "browser-request.json").exists())
            self.assertTrue(marker.exists())


class IndependentFrontendPreflightTests(unittest.TestCase):
    def check(self, component="frontend", rows=None, identity_error=None):
        binding = {"component": component, "candidate_commit": "a" * 40}
        api = {**binding, "component": "api"}
        plan = {
            "bindings": {"api": api},
            "baseline": {env: {"old_runtime": True} for env in r.ENV},
            "history_baseline": {env: {"old-owned-row": "preserved"} for env in r.ENV},
        }
        inventory = {name: {} for name in r.TARGET.values()}
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(r, "validate_plan", return_value=(None, plan))
            )
            stack.enter_context(patch.object(r, "inventory", return_value=inventory))
            stack.enter_context(patch.object(r, "authenticated_state"))
            stack.enter_context(
                patch.object(
                    r,
                    "history",
                    return_value=rows
                    or {
                        "old-owned-row": "preserved",
                        "qualified-api-owned-row": "retained",
                    },
                )
            )
            stack.enter_context(patch.object(r, "probe_cpu_limit", return_value="1"))
            stack.enter_context(
                patch.object(
                    r.shutil,
                    "disk_usage",
                    return_value=type("Disk", (), {"free": 20 * 1024**3})(),
                )
            )
            stack.enter_context(patch.object(r, "unchanged"))
            accepted = stack.enter_context(
                patch.object(frontend_runner, "accepted_api")
            )
            identity = stack.enter_context(
                patch.object(r, "local_identity", side_effect=identity_error)
            )
            result = r.preflight(binding)
            accepted.assert_called_once_with(plan)
            self.assertEqual(
                [call.args for call in identity.call_args_list],
                [(api, env, plan) for env in r.ENV],
            )
            return result

    def test_newly_accepted_api_and_its_terminal_records_are_retained(self):
        self.assertEqual(self.check()["provider_writes"], 0)

    def test_modified_older_journal_record_refuses_frontend_qualification(self):
        with self.assertRaisesRegex(r.Refused, "JOURNAL_HISTORY_CHANGED"):
            self.check(rows={"old-owned-row": "modified"})

    def test_wrong_running_api_identity_refuses_frontend_qualification(self):
        with self.assertRaisesRegex(r.Refused, "ACTUAL_RUNNING_SOURCE"):
            self.check(
                identity_error=r.Refused("ACTUAL_RUNNING_SOURCE_OR_IMAGE_MISMATCH")
            )
