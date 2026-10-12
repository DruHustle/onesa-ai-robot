"""A provider-bound staging device cannot be reused for another source or production."""

import os
import tempfile
import unittest
from unittest.mock import patch

import edge_fixture as fixture
from evidence import REPOSITORY, Rejected


class EdgeFixtureTests(unittest.TestCase):
    def test_private_identity_round_trip_and_foreign_candidate_denial(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "RUNNER_TEMP": directory,
                    "GITHUB_REPOSITORY": REPOSITORY,
                    "GITHUB_REF": "refs/heads/staging",
                    "GITHUB_SHA": "a" * 40,
                },
                clear=True,
            ),
        ):
            fixture.remember({"ROBOT_EDGE_DEVICE_ID": "synthetic-device"})
            self.assertEqual(fixture.path().stat().st_mode & 0o777, 0o600)
            fixture.restore("Production")
            self.assertNotIn("ROBOT_EDGE_DEVICE_ID", os.environ)
            fixture.restore("Staging")
            self.assertEqual(os.environ.pop("ROBOT_EDGE_DEVICE_ID"), "synthetic-device")
            os.environ["GITHUB_SHA"] = "b" * 40
            with self.assertRaises(Rejected):
                fixture.restore("Staging")

    def test_wrong_repository_or_branch_cannot_write_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            for changes in [
                {"GITHUB_REPOSITORY": "foreign/robot"},
                {"GITHUB_REF": "refs/heads/main"},
            ]:
                with (
                    patch.dict(
                        os.environ,
                        {
                            "RUNNER_TEMP": directory,
                            "GITHUB_REPOSITORY": REPOSITORY,
                            "GITHUB_REF": "refs/heads/staging",
                            "GITHUB_SHA": "a" * 40,
                            **changes,
                        },
                        clear=True,
                    ),
                    self.assertRaises(Rejected),
                ):
                    fixture.remember({"ROBOT_EDGE_DEVICE_ID": "synthetic-device"})

    def test_private_permissions_and_existing_binding_are_required(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "RUNNER_TEMP": directory,
                    "GITHUB_REPOSITORY": REPOSITORY,
                    "GITHUB_REF": "refs/heads/staging",
                    "GITHUB_SHA": "a" * 40,
                },
                clear=True,
            ),
        ):
            fixture.remember({"ROBOT_EDGE_DEVICE_ID": "synthetic-device"})
            with self.assertRaises(Rejected):
                fixture.remember({"ROBOT_EDGE_DEVICE_ID": "another-device"})
            fixture.path().chmod(0o644)
            with self.assertRaises(Rejected):
                fixture.restore("Staging")
