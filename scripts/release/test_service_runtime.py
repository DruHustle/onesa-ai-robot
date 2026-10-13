"""A native staging service never weakens production or dependency integrity."""

import unittest

import service_runtime as runtime


class ServiceRuntimeTests(unittest.TestCase):
    def service(self, kind="python", **changes):
        return {
            "serviceDetails": {
                "runtime": kind,
                "envSpecificDetails": {**runtime.layout({"runtime": kind}), **changes},
            }
        }

    def test_native_hash_locked_commands_are_staging_only(self):
        service = self.service()
        self.assertTrue(runtime.allowed(service, "Staging"))
        self.assertFalse(runtime.allowed(service, "Production"))
        self.assertTrue(runtime.allowed(service, "Production", durable_remote=True))
        self.assertFalse(runtime.allowed(service, "Unknown", durable_remote=True))

    def test_unlocked_dependencies_or_extra_workers_cannot_qualify(self):
        for changes in [
            {"buildCommand": "pip install -r requirements.lock"},
            {"startCommand": "uvicorn robot_api.main:create_app --workers 2"},
        ]:
            self.assertFalse(runtime.allowed(self.service(**changes), "Staging"))

    def test_docker_requires_exact_reviewed_build_context(self):
        self.assertTrue(runtime.allowed(self.service("docker"), "Production"))
        for changes in [
            {"dockerfilePath": "../other/Dockerfile"},
            {"dockerContext": ".."},
            {"dockerCommand": "unreviewed"},
        ]:
            self.assertFalse(
                runtime.allowed(self.service("docker", **changes), "Staging")
            )

    def test_unknown_and_conflicting_runtime_are_rejected(self):
        self.assertFalse(
            runtime.allowed(
                {
                    "serviceDetails": {
                        "runtime": "python",
                        "env": "docker",
                        "envSpecificDetails": runtime.layout({"runtime": "docker"}),
                    }
                },
                "Production",
            )
        )
        self.assertFalse(
            runtime.allowed({"serviceDetails": {"runtime": "node"}}, "Staging")
        )
