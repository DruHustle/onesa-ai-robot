"""Synthetic failure evidence keeps wire/JSON errors distinct from assertions."""

import io
import json
import os
import socket
import ssl
import unittest
import urllib.error
from email.message import Message
from unittest.mock import Mock, patch

import smoke


class Diagnostics(unittest.TestCase):
    def test_http_status_preserved(self):
        self.assertEqual(
            smoke.failure_details(smoke.SimulatorHTTPFailure(409)),
            {"category": "http_status", "http_status": 409},
        )

    def test_invalid_json_remains_failure_without_body_text(self):
        error = json.JSONDecodeError("secret message", "private-body", 0)
        self.assertEqual(
            smoke.failure_details(error),
            {"category": "response_json", "body_characters": 12},
        )

    def test_direct_timeout(self):
        self.assertEqual(
            smoke.failure_details(TimeoutError("secret")),
            {"category": "transport_timeout"},
        )

    def test_wrapped_timeout(self):
        self.assertEqual(
            smoke.failure_details(urllib.error.URLError(TimeoutError("secret"))),
            {"category": "transport_timeout"},
        )

    def test_tls(self):
        self.assertEqual(
            smoke.failure_details(urllib.error.URLError(ssl.SSLError("secret"))),
            {"category": "transport_tls"},
        )

    def test_dns(self):
        self.assertEqual(
            smoke.failure_details(urllib.error.URLError(socket.gaierror(-2, "secret"))),
            {"category": "transport_dns"},
        )

    def test_socket(self):
        self.assertEqual(
            smoke.failure_details(
                urllib.error.URLError(ConnectionResetError(104, "secret"))
            ),
            {"category": "transport_socket", "errno": 104},
        )

    def test_errno_bound(self):
        self.assertEqual(
            smoke.failure_details(urllib.error.URLError(OSError(123456, "secret"))),
            {"category": "transport_socket", "errno": None},
        )

    def test_unknown_transport_redacted(self):
        self.assertEqual(
            smoke.failure_details(
                urllib.error.URLError("https://private.invalid/token")
            ),
            {"category": "transport_unclassified"},
        )

    def test_assertion_keeps_acceptance(self):
        self.assertEqual(
            smoke.failure_details(smoke.Rejected("private state")),
            {"category": "acceptance"},
        )

    def test_original_wire_check_still_requires_409_and_valid_json(self):
        api = smoke.Simulator("https://synthetic.vercel.app")
        headers = Message()
        headers["Content-Type"] = "application/json"
        response = urllib.error.HTTPError(
            "https://synthetic.vercel.app/api/v1/tasks/synthetic/approve",
            409,
            "Conflict",
            headers,
            io.BytesIO(b'{"detail":"Task cannot be replayed"}'),
        )
        api.opener = Mock()
        api.opener.open.side_effect = response
        self.assertEqual(
            api.call("/api/v1/tasks/synthetic/approve", {}, expected=409),
            {"detail": "Task cannot be replayed"},
        )
        self.assertEqual(api.opener.open.call_count, 1)
        api.opener.open.side_effect = urllib.error.HTTPError(
            "https://synthetic.vercel.app/api/v1/tasks/synthetic/approve",
            409,
            "Conflict",
            headers,
            io.BytesIO(b"not-json"),
        )
        with self.assertRaises(json.JSONDecodeError):
            api.call("/api/v1/tasks/synthetic/approve", {}, expected=409)
        self.assertEqual(api.opener.open.call_count, 2)

    def test_actual_acceptance_wires_safe_transport_category(self):
        env = {
            "ROBOT_TEST_PASSWORD": "synthetic-private-password",
            "ROBOT_TEST_OPERATOR": "operator",
            "ROBOT_TEST_SCOPE": "approved-synthetic-staging",
        }
        ready = {
            "mode": "simulation",
            "physical_actuation": False,
            "deployment_environment": "staging",
            "storage_mode": "ephemeral-simulation",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(
                smoke.Simulator,
                "call",
                side_effect=[
                    b"Software simulation",
                    ready,
                    urllib.error.URLError(ConnectionResetError(104, "secret URL")),
                ],
            ),
        ):
            record = smoke.run("https://synthetic.vercel.app", "Staging")
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(
            record["failure"],
            {"phase": "authentication", "category": "transport_socket", "errno": 104},
        )
        self.assertNotIn("secret", json.dumps(record))
        self.assertNotIn("synthetic-private", json.dumps(record))
