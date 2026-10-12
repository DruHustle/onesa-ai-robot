"""Staging configuration cannot select production or change private values."""

import os
import unittest
from unittest.mock import patch

import staging_configuration as stage
from evidence import REPOSITORY, Rejected


class StagingConfigurationTests(unittest.TestCase):
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
                "healthCheckPath": "/api/v1/ready",
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
                stage, "provider", side_effect=[self.service(), {}, self.service(), []]
            ) as provider,
        ):
            result = stage.inspect_or_repair(True)
        mutation = provider.call_args_list[1]
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
