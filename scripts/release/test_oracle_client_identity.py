"""Owner observations retain authentication and identify their actual HTTP client."""

import io
import json
import unittest
from unittest.mock import patch

import oracle_robot as r
import oracle_robot_probe as probe


class ClientIdentityTests(unittest.TestCase):
    def response(self, value):
        result = io.BytesIO(json.dumps(value).encode())
        result.status = 200
        return result

    def test_preflight_identifies_every_request_and_retains_csrf_logout(self):
        seen = []

        def open_request(request, **kwargs):
            seen.append(request)
            self.assertEqual(
                request.get_header("User-agent"), "OnesaOracleRobotOwner/1"
            )
            self.assertEqual(request.get_header("Origin"), "https://robot.onesa.eu")
            self.assertTrue(
                request.full_url.startswith("https://robot-api.onesa.eu/api/v1/")
            )
            if request.full_url.endswith("/ready"):
                return self.response(
                    {
                        "mode": "simulation",
                        "physical_actuation": False,
                        "deployment_environment": "production",
                        "storage_mode": "turso",
                    }
                )
            if request.full_url.endswith("/auth/login"):
                self.assertEqual(json.loads(request.data)["password"], "synthetic-only")
                return self.response({"csrf": "fixture-csrf"})
            if request.full_url.endswith("/status"):
                return self.response(
                    {
                        "stopped": True,
                        "active_task": None,
                        "physical_actuation": False,
                        "mode": "simulation",
                    }
                )
            self.assertTrue(request.full_url.endswith("/auth/logout"))
            self.assertEqual(request.get_header("X-csrf-token"), "fixture-csrf")
            return self.response({})

        with (
            patch.object(
                r,
                "credentials",
                return_value={
                    "production": {"operator": "fixture", "password": "synthetic-only"}
                },
            ),
            patch.object(
                r,
                "runtime_values",
                return_value={"ROBOT_PUBLIC_ORIGIN": "https://robot.onesa.eu"},
            ),
            patch.object(r.urllib.request, "build_opener") as opener,
        ):
            opener.return_value.open.side_effect = open_request
            r.authenticated_state(
                {},
                "production",
                {"api_origins": {"production": "https://robot-api.onesa.eu"}},
            )
        self.assertEqual(len(seen), 4)

    def test_probe_retains_origin_csrf_and_explicit_staging_protection(self):
        api = probe.API(
            "https://robot-api-staging.onesa.eu",
            "https://fixture.vercel.app",
            {},
            bypass="synthetic-bypass",
        )
        api.csrf = "synthetic-csrf"
        with patch.object(api.opener, "open", return_value=self.response({})) as opener:
            api.call("/api/v1/ready")
            request = opener.call_args.args[0]
            self.assertEqual(
                request.get_header("User-agent"), "OnesaOracleRobotOwner/1"
            )
            self.assertEqual(request.get_header("Origin"), "https://fixture.vercel.app")
            self.assertEqual(request.get_header("X-csrf-token"), "synthetic-csrf")
            self.assertEqual(
                request.get_header("X-vercel-protection-bypass"), "synthetic-bypass"
            )


if __name__ == "__main__":
    unittest.main()
