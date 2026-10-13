"""Staging configuration cannot select production or change private values."""

import hashlib
import json
import os
import unittest
from unittest.mock import patch

import staging_configuration as stage
from evidence import REPOSITORY, Rejected


class StagingConfigurationTests(unittest.TestCase):
    def test_edge_credential_diagnostics_are_boolean_only_and_never_reveal_values(self):
        token = "synthetic-private-edge-marker" * 3
        stored = hashlib.sha256(token.encode()).hexdigest()
        for supplied, expected in [
            (token, True),
            ("wrong-private-marker" * 4, False),
            ("", False),
        ]:
            with patch.dict(os.environ, {"ROBOT_EDGE_TOKEN": supplied}, clear=True):
                report = stage.edge_credential_report(
                    {"ROBOT_EDGE_TOKEN_SHA256": stored}
                )
            self.assertEqual(report["edge_test_token_matches"], expected)
            self.assertTrue(all(type(v) is bool for v in report.values()))
            self.assertNotIn("private", json.dumps(report))
            self.assertNotIn(stored, json.dumps(report))

    def test_frontend_repair_refuses_production_before_any_provider_access(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_REPOSITORY": REPOSITORY,
                    "GITHUB_REF": "refs/heads/main",
                    "GITHUB_ACTOR": "DruHustle",
                    "RUNNER_ENVIRONMENT": "github-hosted",
                },
                clear=True,
            ),
            patch.object(stage, "provider") as provider,
        ):
            with self.assertRaises(Rejected):
                stage.frontend_binding(repair=True)
            provider.assert_not_called()

    def context(self):
        return {
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_ACTOR": "DruHustle",
            "RUNNER_ENVIRONMENT": "github-hosted",
            "GITHUB_REF": "refs/heads/staging",
            "RENDER_SERVICE_ID": stage.SERVICE,
            "RENDER_API_KEY": "synthetic",
        }

    def service(self):
        return {
            "id": stage.SERVICE,
            "repo": "https://github.com/" + REPOSITORY,
            "type": "web_service",
            "branch": "staging",
            "autoDeployTrigger": "off",
            "rootDir": "onesa-ai-robot-backend",
            "serviceDetails": {
                "env": "docker",
                "plan": "free",
                "region": "frankfurt",
                "url": stage.API,
                "healthCheckPath": "/api/v1/health",
                "envSpecificDetails": {
                    "dockerfilePath": "./Dockerfile",
                    "dockerContext": ".",
                    "dockerCommand": "",
                },
            },
        }

    def test_unauthorized_context_is_rejected_before_provider_access(self):
        for change in [
            {"GITHUB_ACTOR": "foreign"},
            {"GITHUB_REF": "refs/heads/main"},
            {"RUNNER_ENVIRONMENT": "self-hosted"},
            {"RENDER_SERVICE_ID": "srv-production"},
        ]:
            with (
                patch.dict(os.environ, {**self.context(), **change}, clear=True),
                patch.object(stage, "provider") as provider,
                self.assertRaises(Rejected),
            ):
                stage.inspect_or_repair(True)
            provider.assert_not_called()

    def test_existing_identity_plan_and_product_are_mandatory(self):
        for change in [
            {"id": "srv-production"},
            {"repo": "https://github.com/foreign/robot"},
            {"serviceDetails": {**self.service()["serviceDetails"], "plan": "starter"}},
        ]:
            with self.assertRaises(Rejected):
                stage.target({**self.service(), **change})

    def test_repair_changes_only_nonsecret_staging_layout(self):
        with (
            patch.dict(os.environ, self.context(), clear=True),
            patch.object(
                stage,
                "provider",
                side_effect=[
                    self.service(),
                    [
                        {
                            "envVar": {
                                "key": "ROBOT_ACTUATION_ENABLED",
                                "value": "false",
                            }
                        },
                        {
                            "envVar": {
                                "key": "ROBOT_DEPLOYMENT_ENVIRONMENT",
                                "value": "staging",
                            }
                        },
                    ],
                    {},
                    self.service(),
                ],
            ) as provider,
        ):
            result = stage.inspect_or_repair(True)
        mutation = provider.call_args_list[2]
        self.assertEqual(mutation.kwargs, {"method": "PATCH"})
        self.assertEqual(
            set(mutation.args[2]),
            {"autoDeployTrigger", "branch", "rootDir", "serviceDetails"},
        )
        self.assertFalse(result["credentials_changed"])
        self.assertFalse(result["database_modified"])
        self.assertFalse(result["deployment_requested"])

    def test_top_level_runtime_is_checked_without_admitting_native_or_unknown(self):
        service = self.service()
        service["serviceDetails"].pop("env")
        stage.target({**service, "runtime": "docker"})
        for runtime in ["python", None, "node"]:
            with self.assertRaises(Rejected):
                stage.target({**service, "runtime": runtime})

    def test_current_runtime_field_takes_precedence_over_empty_legacy_env(self):
        service = self.service()
        service["serviceDetails"].update(runtime="docker", env=None)
        stage.target(service)
        service["serviceDetails"]["runtime"] = "python"
        with self.assertRaises(Rejected):
            stage.target(service)

    def test_read_only_native_inventory_does_not_authorize_repair(self):
        service = self.service()
        service["serviceDetails"].update(runtime="python", env=None)
        with (
            patch.dict(os.environ, self.context(), clear=True),
            patch.object(stage, "provider", side_effect=[service, []]) as provider,
        ):
            result = stage.inspect_or_repair(False)
        self.assertEqual(result["runtime_kind"], "python")
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["layout_changed"])
        self.assertEqual(len(provider.call_args_list), 2)
        self.assertTrue(all(len(call.args) == 2 for call in provider.call_args_list))
        with (
            patch.dict(os.environ, self.context(), clear=True),
            patch.object(stage, "provider", return_value=service) as provider,
            self.assertRaises(Rejected),
        ):
            stage.inspect_or_repair(True)
        self.assertEqual(len(provider.call_args_list), 2)

    def test_native_staging_layout_preserves_private_values_and_blocks_physical_mode(
        self,
    ):
        from service_runtime import layout

        service = self.service()
        service["serviceDetails"].update(
            runtime="python", env=None, envSpecificDetails=layout({"runtime": "python"})
        )
        settings = {
            "ROBOT_ACTUATION_ENABLED": "false",
            "ROBOT_DEPLOYMENT_ENVIRONMENT": "staging",
            "ROBOT_STORAGE_MODE": "turso",
        }
        entries = [
            {"envVar": {"key": key, "value": value}} for key, value in settings.items()
        ]
        with (
            patch.dict(os.environ, self.context(), clear=True),
            patch.object(
                stage, "provider", side_effect=[service, entries, {}, service]
            ) as provider,
        ):
            result = stage.inspect_or_repair(True)
        self.assertTrue(result["layout_verified"])
        self.assertFalse(result["credentials_changed"])
        self.assertEqual(
            provider.call_args_list[2].args[2]["serviceDetails"]["envSpecificDetails"],
            layout({"runtime": "python"}),
        )
        for changes in [
            {"ROBOT_ACTUATION_ENABLED": "true"},
            {"ROBOT_DEPLOYMENT_ENVIRONMENT": "production"},
            {"ROBOT_STORAGE_MODE": "persistent"},
        ]:
            bad = [
                {"envVar": {"key": key, "value": value}}
                for key, value in {**settings, **changes}.items()
            ]
            with (
                patch.dict(os.environ, self.context(), clear=True),
                patch.object(stage, "provider", side_effect=[service, bad]) as provider,
                self.assertRaises(Rejected),
            ):
                stage.inspect_or_repair(True)
            self.assertEqual(len(provider.call_args_list), 2)
