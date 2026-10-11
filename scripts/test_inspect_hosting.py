"""Ensure owner diagnostics never serialize provider secrets or authorize a deploy."""

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import inspect_hosting as inspection


class InspectionTests(unittest.TestCase):
    def test_provider_values_are_never_emitted(self):
        secret = "synthetic-sensitive-fixture-must-not-be-emitted"

        def response(origin, path, token):
            if "env-vars" in path:
                return [{"envVar": {"key": key, "value": secret}}
                        for key in inspection.KEYS], 200
            if "/deploys" in path:
                return [{"deploy": {"status": "live", "message": secret}}], 200
            if path.startswith("/v9") and "/env?" in path:
                return {"envs": [{"key": "ROBOT_API_URL", "value": secret,
                                  "target": ["production"]}]}, 200
            return {"untrusted_provider_message": secret}, 200

        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "DruHustle/onesa-ai-robot",
                                    "VERCEL_PROJECT_ID": "fixture", "VERCEL_ORG_ID": "fixture"}), \
                patch.object(inspection, "read", side_effect=response):
            stream = io.StringIO()
            with redirect_stdout(stream):
                inspection.main()
        self.assertNotIn(secret, stream.getvalue())
        record = json.loads(stream.getvalue())
        self.assertFalse(record["deployment_requested"])
        self.assertTrue(record["production"]["configured"]["ROBOT_OPERATOR_PASSWORD_HASH"])

    def test_missing_provider_access_is_not_verified(self):
        with patch.object(inspection, "read", return_value=({}, 403)):
            record = inspection.render("fixture")
        self.assertEqual(record["api_http"], 403)
        self.assertFalse(record["environment_inventory_complete"])
        self.assertFalse(record["physical_actuation_disabled"])
        self.assertIsNone(inspection.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid"))


if __name__ == "__main__":
    unittest.main()
