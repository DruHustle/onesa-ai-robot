"""Release/provider failure paths with synthetic fixtures only."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cloud
import evidence
import smoke


class CloudTests(unittest.TestCase):
    def test_failed_cli_acceptance_persists_private_smoke_before_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "frontend-url.txt").write_text("https://synthetic.vercel.app")
            record = {"status": "FAIL", "checks": {"authentication": "FAIL"}}
            with (
                patch("edge_fixture.restore"),
                patch.object(smoke, "run", return_value=record),
                self.assertRaises(evidence.Rejected),
            ):
                smoke.main(["Staging", "--directory", directory])
            self.assertEqual(json.loads((path / "smoke.json").read_text()), record)
            self.assertEqual((path / "smoke.json").stat().st_mode & 0o777, 0o600)
            self.assertFalse((path / "record.json").exists())
            with self.assertRaises(evidence.Rejected):
                evidence.save(record, path / "smoke.json")

    def test_passed_cli_acceptance_keeps_smoke_and_final_record_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "frontend-url.txt").write_text("https://synthetic.vercel.app")
            record = {"status": "PASS", "checks": {"authentication": "PASS"}}
            with (
                patch("edge_fixture.restore"),
                patch.object(smoke, "run", return_value=record),
            ):
                smoke.main(["Staging", "--directory", directory])
            self.assertEqual(json.loads((path / "smoke.json").read_text()), record)
            self.assertEqual(
                sorted(p.name for p in path.iterdir()),
                ["frontend-url.txt", "smoke.json"],
            )

    def test_only_staging_turso_uses_a_remote_journal_instead_of_a_filesystem(self):
        self.assertFalse(cloud.filesystem_required("Staging", "turso"))
        for environment, mode in [
            ("Production", "turso"),
            ("Production", "persistent"),
            ("Staging", "persistent"),
            ("Staging", "ephemeral-simulation"),
            ("Staging", "unknown"),
        ]:
            self.assertTrue(cloud.filesystem_required(environment, mode))

    def test_cloud_diagnostics_never_echo_arbitrary_provider_values(self):
        self.assertEqual(
            cloud.safe_failure_code(evidence.Rejected("Isolated database required")),
            "DATABASE_PATH",
        )
        for error in [
            evidence.Rejected("private-provider-marker"),
            KeyError("private-key-marker"),
            ValueError("private-value-marker"),
        ]:
            self.assertNotIn("private", cloud.safe_failure_code(error))

    def test_native_preview_reuse_rejects_duplicates_wrong_source_and_production(self):
        candidate = {
            "meta": {"githubCommitSha": "a" * 40, "githubCommitRef": "staging"},
            "target": None,
            "readyState": "READY",
            "url": "synthetic.vercel.app",
        }
        env = {
            "GITHUB_SHA": "a" * 40,
            "VERCEL_PROJECT_ID": "prj_synthetic",
            "VERCEL_ORG_ID": "team_synthetic",
            "VERCEL_TOKEN": "synthetic-only",
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, env, clear=True),
            patch.object(cloud, "preflight"),
            patch.object(cloud, "frontend") as verify,
        ):
            for items in [
                [candidate, candidate],
                [{**candidate, "target": "production"}],
                [
                    {
                        **candidate,
                        "meta": {
                            "githubCommitSha": "b" * 40,
                            "githubCommitRef": "staging",
                        },
                    }
                ],
            ]:
                with (
                    patch.object(
                        cloud, "provider", return_value={"deployments": items}
                    ),
                    self.assertRaises(evidence.Rejected),
                ):
                    cloud.resolve_preview(directory, attempts=1)
                self.assertFalse(Path(directory, "frontend-url.txt").exists())
            with patch.object(
                cloud, "provider", return_value={"deployments": [candidate]}
            ) as provider:
                self.assertEqual(
                    cloud.resolve_preview(directory, attempts=1),
                    "https://synthetic.vercel.app",
                )
                self.assertEqual(
                    len(provider.call_args.args), 2
                )  # GET only, no mutation payload.
                verify.assert_called_once_with(
                    "https://synthetic.vercel.app", "Staging"
                )

    def test_missing_probe_credentials_cannot_pass(self):
        with patch.dict(os.environ, {}, clear=True):
            result = smoke.run("https://synthetic.vercel.app", "Staging")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn("PASS", result["checks"].values())

    def test_no_redirect_credentials_or_untrusted_origins(self):
        for url in [
            "http://test.vercel.app",
            "https://user:secret@test.vercel.app",
            "https://test.vercel.app?token=secret",
            "https://attacker.invalid",
            "https://test.vercel.app/private",
        ]:
            with self.subTest(url=url), self.assertRaises(evidence.Rejected):
                cloud.origin(url, ".vercel.app")

    def test_production_render_free_storage_cannot_pass(self):
        service = {
            "repo": "https://github.com/" + evidence.REPOSITORY,
            "branch": "main",
            "type": "web_service",
            "rootDir": "onesa-ai-robot-backend",
            "autoDeployTrigger": "off",
            "serviceDetails": {
                "plan": "free",
                "env": "docker",
                "envSpecificDetails": {
                    "dockerfilePath": "./Dockerfile",
                    "dockerContext": ".",
                    "dockerCommand": "",
                },
                "url": "https://synthetic.onrender.com",
            },
        }
        values = {
            "ROBOT_ACTUATION_ENABLED": "false",
            "ROBOT_DEPLOYMENT_ENVIRONMENT": "production",
            "ROBOT_DATABASE_PATH": "/app/storage/robot.sqlite3",
            "ROBOT_OPERATOR_PASSWORD_HASH": "scrypt$synthetic",
            "ROBOT_STORAGE_MODE": "persistent",
            "ROBOT_EDGE_DEVICE_ID": "synthetic-ci",
            "ROBOT_EDGE_TOKEN_SHA256": "a" * 64,
        }
        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_REF": "refs/heads/main",
                    "RENDER_SERVICE_ID": "srv-synthetic",
                    "ROBOT_API_URL": "https://synthetic.onrender.com",
                    "RENDER_API_KEY": "synthetic",
                },
                clear=True,
            ),
            patch.object(
                cloud,
                "provider",
                side_effect=[
                    service,
                    [
                        {"envVar": {"key": key, "value": value}}
                        for key, value in values.items()
                    ],
                ],
            ),
            self.assertRaisesRegex(evidence.Rejected, "Production BLOCKED"),
        ):
            cloud.preflight("Production")

    def test_canonical_production_origin_rejects_wrong_commit(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_SHA": "a" * 40,
                    "VERCEL_PROJECT_ID": "prj_synthetic",
                    "VERCEL_ORG_ID": "team_synthetic",
                    "VERCEL_TOKEN": "synthetic-only",
                },
                clear=True,
            ),
            patch.object(
                cloud,
                "provider",
                return_value={
                    "projectId": "prj_synthetic",
                    "readyState": "READY",
                    "target": "production",
                    "meta": {"githubCommitSha": "b" * 40},
                    "id": "dpl_synthetic",
                },
            ),
            self.assertRaises(evidence.Rejected),
        ):
            cloud.frontend("https://robot.synthetic.example.com", "Production")

    def test_cloud_review_cannot_approve_hardware(self):
        record = {
            "CODE_VERIFIED": "PASS",
            "STAGING_VERIFIED": "PASS",
            "scope": "software-and-simulation-only",
            "SIMULATION_VERIFIED": "PASS",
            "ROBOT_SAFETY_SOFTWARE_VERIFIED": "PASS",
            "PHYSICAL_HARDWARE_APPROVED": "PASS",
        }
        with self.assertRaisesRegex(evidence.Rejected, "physical operation"):
            evidence.technical_gate(None, record, "a" * 40)


class TursoStagingTests(unittest.TestCase):
    def test_turso_requires_exact_url_and_token_but_no_token_in_workflow(self):
        url = "libsql://synthetic-staging.example.turso.io"
        values = {
            "ROBOT_STORAGE_MODE": "turso",
            "ROBOT_TURSO_DATABASE_URL": url,
            "ROBOT_TURSO_AUTH_TOKEN": "synthetic-database-token",
        }
        with patch.dict(
            os.environ,
            {
                "ROBOT_STORAGE_MODE": "turso",
                "ROBOT_TURSO_DATABASE_URL": url,
            },
            clear=True,
        ):
            self.assertEqual(cloud.staging_storage(values), "turso")
            for changes in (
                {"ROBOT_TURSO_DATABASE_URL": "libsql://different.example.turso.io"},
                {"ROBOT_TURSO_AUTH_TOKEN": ""},
                {"ROBOT_STORAGE_MODE": "persistent"},
            ):
                with (
                    self.subTest(changes=changes),
                    self.assertRaises(evidence.Rejected),
                ):
                    cloud.staging_storage({**values, **changes})

    def test_default_ephemeral_scope_cannot_silently_accept_turso(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                cloud.staging_storage({"ROBOT_STORAGE_MODE": "ephemeral-simulation"}),
                "ephemeral-simulation",
            )
            with self.assertRaises(evidence.Rejected):
                cloud.staging_storage({"ROBOT_STORAGE_MODE": "turso"})


if __name__ == "__main__":
    unittest.main()
