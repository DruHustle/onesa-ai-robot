"""Release/provider failure paths with synthetic fixtures only."""

import os
import unittest
from unittest.mock import patch

import cloud
import evidence
import smoke


class CloudTests(unittest.TestCase):
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
