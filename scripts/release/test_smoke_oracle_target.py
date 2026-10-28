"""Legacy acceptance target selection; no HTTP, credentials or physical operation."""

import os
import unittest
from unittest.mock import patch

import smoke
from evidence import Rejected


class OracleEdgeTargetTests(unittest.TestCase):
    def test_exact_oracle_staging_needs_no_render_environment_or_actions_identity(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                smoke.edge_backend("Staging", "https://robot-api-staging.onesa.eu"),
                "https://robot-api-staging.onesa.eu",
            )

    def test_production_foreign_or_normalized_alias_never_selects_oracle(self):
        for environment, origin in [
            ("Production", "https://robot-api-staging.onesa.eu"),
            ("Staging", "https://robot-api.onesa.eu"),
            ("Staging", "https://robot-api-staging.onesa.eu.attacker.invalid"),
            ("Staging", "https://robot-api-staging.onesa.eu/"),
            ("Staging", "http://robot-api-staging.onesa.eu"),
            ("Staging", "https://robot-api-staging.onesa.eu:443"),
            ("Staging", "https://name:secret@robot-api-staging.onesa.eu"),
        ]:
            with (
                self.subTest(environment=environment, origin=origin),
                self.assertRaises(Rejected),
            ):
                smoke.edge_backend(environment, origin)

    def test_oracle_production_refused_before_any_simulator_or_login(self):
        with patch.object(smoke, "Simulator") as simulator:
            with self.assertRaises(Rejected):
                smoke.run(
                    "https://robot.onesa.eu",
                    "Production",
                    oracle_staging_api="https://robot-api-staging.onesa.eu",
                )
            simulator.assert_not_called()

    def test_existing_render_path_preserves_both_environment_contracts(self):
        with patch.dict(
            os.environ, {"ROBOT_API_URL": "https://synthetic.onrender.com"}, clear=True
        ):
            for environment in ["Staging", "Production"]:
                self.assertEqual(
                    smoke.edge_backend(environment), "https://synthetic.onrender.com"
                )

    def test_render_default_cannot_silently_accept_the_oracle_or_foreign_api(self):
        for origin in [
            "https://robot-api-staging.onesa.eu",
            "https://attacker.invalid",
        ]:
            with (
                self.subTest(origin=origin),
                patch.dict(os.environ, {"ROBOT_API_URL": origin}, clear=True),
                self.assertRaises(Rejected),
            ):
                smoke.edge_backend("Staging")


if __name__ == "__main__":
    unittest.main()
