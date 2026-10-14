"""Isolated provider state/receipt tests; no live request or qualification attempt."""

import hashlib
import importlib.util
import io
import json
import tempfile
import time
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    "robot_render_deploy", Path(__file__).resolve().parents[1] / "deploy_render.py"
)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
SHA = "a" * 40
OTHER = "b" * 40
ID = "dep-synthetic123"


class Clock:
    value = 0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeRender:
    def __init__(self, clock, states, service=None, failure=None, latest=None):
        self.clock, self.sleep, self.states = clock, clock.sleep, list(states)
        self.service = service or d.TARGETS["Staging"][0]
        self.failure, self.latest, self.calls, self.last = failure, latest, [], None
        self.post_used = False

    def call(self, suffix, payload=None):
        self.calls.append((suffix, payload))
        if self.failure and suffix == self.failure[0]:
            raise self.failure[1]
        if suffix == "":
            return {
                "id": self.service,
                "repo": "https://github.com/" + d.REPOSITORY,
                "branch": "staging",
                "rootDir": "onesa-ai-robot-backend",
                "type": "web_service",
                "autoDeployTrigger": "off",
            }
        if suffix == "/env-vars?limit=100":
            return [
                {"envVar": {"key": k, "value": v}}
                for k, v in {
                    "ROBOT_DEPLOYMENT_ENVIRONMENT": "staging",
                    "ROBOT_ACTUATION_ENABLED": "false",
                }.items()
            ]
        if suffix == "/deploys?limit=20":
            return self.latest or [
                {
                    "deploy": self.deploy("live")
                    if self.last == "live"
                    else {"id": "dep-old", "status": "live", "commit": {"id": OTHER}}
                }
            ]
        if payload is not None:
            self.post_used = True
            return self.deploy("created")
        value = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        self.last = value if isinstance(value, str) else None
        return self.deploy(value) if isinstance(value, str) else value

    def deploy(self, state):
        return {
            "id": ID,
            "status": state,
            "commit": {"id": SHA},
            "createdAt": "2026-10-14T20:02:29Z",
            "updatedAt": "2026-10-14T20:02:29Z",
            "finishedAt": None,
        }


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.preflight = self.root / "preflight.json"
        self.preflight.write_text(
            json.dumps(
                {
                    "repository": d.REPOSITORY,
                    "candidate_commit": SHA,
                    "CODE_VERIFIED": "PASS",
                    "valid_for_source_sha256": "c" * 64,
                    "workflow_run_id": 42,
                }
            )
        )
        self.args = SimpleNamespace(
            preflight=self.preflight,
            receipt=self.root / "render.json",
            environment="Staging",
            observe_id=None,
            candidate=None,
            receipt_sha256=None,
            wait_seconds=20,
            request_timeout=2,
            poll_seconds=5,
            max_poll_seconds=10,
        )
        self.env = {
            "RENDER_SERVICE_ID": d.TARGETS["Staging"][0],
            "RENDER_API_KEY": "synthetic-only",
            "GITHUB_SHA": SHA,
            "GITHUB_REF": "refs/heads/staging",
            "GITHUB_RUN_ID": "42",
            "GITHUB_RUN_ATTEMPT": "1",
        }

    def execute(self, states, **kwargs):
        clock = Clock()
        fake = FakeRender(clock, states, **kwargs)
        with redirect_stdout(io.StringIO()):
            result = d.run(
                self.args,
                self.env,
                client_factory=lambda *a, **k: fake,
                monotonic=clock.now,
            )
        return result, json.loads(self.args.receipt.read_text()), fake

    def resume(self):
        self.args.observe_id = ID
        self.args.candidate = SHA
        self.args.receipt_sha256 = hashlib.sha256(
            self.args.receipt.read_bytes()
        ).hexdigest()
        self.args.preflight = self.root / "render-preflight.json"

    def test_slow_progress_live_receipt_saved_before_any_poll(self):
        observed = []
        original = d.observe

        def check(*args, **kwargs):
            saved = json.loads(self.args.receipt.read_text())
            observed.append(saved["observation_outcome"])
            return original(*args, **kwargs)

        with patch.object(d, "observe", side_effect=check):
            result, receipt, fake = self.execute(
                ["queued", "build_in_progress", "live"]
            )
        self.assertTrue(result)
        self.assertEqual(observed, ["DEPLOYMENT_ACCEPTED_OBSERVATION_PENDING"])
        self.assertEqual(
            [x["status"] for x in receipt["transitions"]],
            ["queued", "build_in_progress", "live"],
        )
        self.assertEqual(sum(payload is not None for _, payload in fake.calls), 1)
        self.assertEqual(receipt["application_acceptance"], "NOT_TESTED")
        self.assertIs(receipt["promotion_authorized"], False)

    def test_each_documented_terminal_failure_is_not_observation_timeout(self):
        for status in sorted(d.FAILED | {"canceled", "deactivated"}):
            with self.subTest(status=status):
                self.args.receipt = self.root / (status + ".json")
                binding = self.root / "render-preflight.json"
                if binding.exists():
                    binding.unlink()
                result, record, _ = self.execute([status])
                self.assertFalse(result)
                self.assertEqual(record["status"], status)
                self.assertEqual(
                    record["provider_failure_confirmed"], status in d.FAILED
                )
                self.assertNotEqual(
                    record["observation_outcome"], "OBSERVATION_TIMEOUT"
                )

    def test_active_timeout_preserves_identity_and_does_not_cancel_or_fail_provider(
        self,
    ):
        result, record, fake = self.execute(["build_in_progress"])
        self.assertFalse(result)
        self.assertEqual(record["observation_outcome"], "OBSERVATION_TIMEOUT")
        self.assertEqual(record["deployment_id"], ID)
        self.assertIs(record["provider_may_continue"], True)
        self.assertIs(record["provider_failure_confirmed"], False)
        self.assertFalse(any("cancel" in route for route, _ in fake.calls))
        self.assertEqual(self.args.receipt.stat().st_mode & 0o777, 0o600)

    def test_resume_same_deployment_never_creates_and_retains_request_provenance(self):
        _, before, _ = self.execute(["build_in_progress"])
        self.resume()
        result, after, fake = self.execute(["live"])
        self.assertTrue(result)
        self.assertEqual(after["request_context"], before["request_context"])
        self.assertEqual(after["observation_continuations"], 1)
        self.assertTrue(all(payload is None for _, payload in fake.calls))

    def test_wrong_service_candidate_environment_or_digest_rejected_before_provider(
        self,
    ):
        self.execute(["build_in_progress"])
        self.resume()
        for key, value in [
            ("candidate", OTHER),
            ("environment", "Production"),
            ("receipt_sha256", "d" * 64),
            ("observe_id", "dep-foreign"),
        ]:
            original = getattr(self.args, key)
            setattr(self.args, key, value)
            factory = Mock()
            with self.subTest(key=key), self.assertRaises(d.DeploymentError):
                d.run(self.args, self.env, client_factory=factory)
            self.assertFalse(factory.called and factory.return_value.call.called)
            setattr(self.args, key, original)

    def test_provider_wrong_service_or_actual_commit_is_rejected(self):
        result, receipt, fake = self.execute(["live"], service="srv-foreign")
        self.assertFalse(result)
        self.assertEqual(receipt["observation_outcome"], "SERVICE_ENVIRONMENT_MISMATCH")
        self.assertFalse(fake.post_used)

    def test_wrong_commit_after_acceptance_preserves_receipt_and_blocks(self):
        result, receipt, _ = self.execute(
            [{"id": ID, "status": "live", "commit": {"id": OTHER}}]
        )
        self.assertFalse(result)
        self.assertEqual(receipt["observation_outcome"], "DEPLOYMENT_IDENTITY_MISMATCH")

    def test_unknown_malformed_status_or_timestamp_never_becomes_success(self):
        for value in ["future_state", [], None, {"private": "marker"}]:
            with self.subTest(value=value):
                self.args.receipt = self.root / (
                    "case" + str(len(list(self.root.glob("case*")))) + ".json"
                )
                binding = self.root / "render-preflight.json"
                if binding.exists():
                    binding.unlink()
                result, record, _ = self.execute(
                    [{"id": ID, "commit": {"id": SHA}, "status": value}]
                )
                self.assertFalse(result)
                self.assertEqual(
                    record["observation_outcome"], "UNKNOWN_PROVIDER_STATE"
                )
                self.assertNotIn("marker", self.args.receipt.read_text())

    def test_authentication_failure_is_clear_and_receipt_is_preserved(self):
        result, record, fake = self.execute(
            ["live"], failure=("", d.DeploymentError("AUTHENTICATION_DENIED", 401))
        )
        self.assertFalse(result)
        self.assertEqual(record["http_status"], 401)
        self.assertFalse(fake.post_used)

    def test_ambiguous_create_is_never_retried_and_intent_blocks_repeat(self):
        result, record, fake = self.execute(
            ["live"], failure=("/deploys", d.DeploymentError("SUBMISSION_UNCERTAIN"))
        )
        self.assertFalse(result)
        self.assertEqual(record["observation_outcome"], "SUBMISSION_UNCERTAIN")
        self.assertTrue(record["provider_may_continue"])
        self.assertEqual(sum(x is not None for _, x in fake.calls), 1)
        with self.assertRaises(FileExistsError):
            self.execute(["live"])

    def test_live_but_superseded_is_not_a_success(self):
        # Initial list must permit create, but final readback supersedes it.
        clock = Clock()
        fake = FakeRender(clock, ["live"])
        original = fake.call

        def call(route, body=None):
            if route == "/deploys?limit=20" and fake.post_used:
                return [
                    {
                        "deploy": {
                            "id": "dep-newer",
                            "status": "queued",
                            "commit": {"id": OTHER},
                        }
                    }
                ]
            return original(route, body)

        fake.call = call
        with redirect_stdout(io.StringIO()):
            result = d.run(
                self.args,
                self.env,
                client_factory=lambda *a, **k: fake,
                monotonic=clock.now,
            )
        self.assertFalse(result)
        self.assertEqual(
            json.loads(self.args.receipt.read_text())["observation_outcome"],
            "LIVE_BUT_SUPERSEDED_PROMOTION_BLOCKED",
        )

    def test_existing_active_or_same_candidate_prevents_duplicate_create(self):
        for deploy in [
            {"id": "dep-existing", "status": "queued", "commit": {"id": OTHER}},
            {"id": ID, "status": "canceled", "commit": {"id": SHA}},
        ]:
            self.args.receipt = self.root / (deploy["status"] + ".json")
            binding = self.root / "render-preflight.json"
            if binding.exists():
                binding.unlink()
            result, _, fake = self.execute(["live"], latest=[{"deploy": deploy}])
            self.assertFalse(result)
            self.assertFalse(fake.post_used)

    def test_receipt_unknown_fields_and_promoted_claims_rejected_before_network(self):
        self.execute(["build_in_progress"])
        self.resume()
        original = self.args.receipt.read_text()
        for change in [
            {"secret": "synthetic-private-marker"},
            {"promotion_authorized": True},
        ]:
            value = {**json.loads(original), **change}
            self.args.receipt.write_text(json.dumps(value))
            self.args.receipt_sha256 = hashlib.sha256(
                self.args.receipt.read_bytes()
            ).hexdigest()
            factory = Mock()
            with self.assertRaises(d.DeploymentError):
                d.run(self.args, self.env, client_factory=factory)
            self.assertFalse(factory.return_value.call.called)

    def test_read_only_binding_cannot_authorize_a_create(self):
        value = json.loads(self.preflight.read_text())
        self.preflight.write_text(json.dumps(d.preflight_binding(value, SHA)))
        with self.assertRaises(d.DeploymentError):
            self.execute(["live"])

    def test_every_active_state_can_progress_to_live(self):
        for state in sorted(d.ACTIVE):
            self.args.receipt = self.root / (state + ".json")
            binding = self.root / "render-preflight.json"
            if binding.exists():
                binding.unlink()
            result, record, _ = self.execute([state, "live"])
            self.assertTrue(result)
            self.assertEqual(record["transitions"][0]["status"], state)

    def test_provider_environment_or_physical_flag_mismatch_blocks_before_create(self):
        clock = Clock()
        fake = FakeRender(clock, ["live"])
        original = fake.call

        def call(route, body=None):
            if route == "/env-vars?limit=100":
                return [
                    {
                        "envVar": {
                            "key": "ROBOT_DEPLOYMENT_ENVIRONMENT",
                            "value": "production",
                        }
                    },
                    {"envVar": {"key": "ROBOT_ACTUATION_ENABLED", "value": "true"}},
                ]
            return original(route, body)

        fake.call = call
        with redirect_stdout(io.StringIO()):
            result = d.run(
                self.args,
                self.env,
                client_factory=lambda *a, **k: fake,
                monotonic=clock.now,
            )
        self.assertFalse(result)
        self.assertFalse(fake.post_used)

    def test_provider_timestamp_cannot_copy_arbitrary_private_text_into_receipt(self):
        value = FakeRender(Clock(), ["live"]).deploy("live")
        value["updatedAt"] = "synthetic-private-marker"
        result, record, _ = self.execute([value])
        self.assertFalse(result)
        self.assertEqual(record["observation_outcome"], "PROVIDER_TIMESTAMP_REJECTED")
        self.assertNotIn("synthetic-private-marker", self.args.receipt.read_text())

    def test_long_unchanged_state_logs_periodic_summaries_not_every_poll(self):
        self.args.wait_seconds = 600
        output = io.StringIO()
        clock = Clock()
        fake = FakeRender(clock, ["build_in_progress"])
        with redirect_stdout(output):
            result = d.run(
                self.args,
                self.env,
                client_factory=lambda *a, **k: fake,
                monotonic=clock.now,
            )
        self.assertFalse(result)
        polls = sum(route.endswith(ID) for route, _ in fake.calls)
        self.assertGreater(polls, 50)
        self.assertLess(len(output.getvalue().splitlines()), 10)

    def test_workflow_saves_observation_before_acceptance_and_on_failure(self):
        for name in ["release-staging.yml", "deploy.yml"]:
            text = (
                Path(__file__).resolve().parents[2] / ".github/workflows" / name
            ).read_text()
            self.assertTrue("name: render-deployment-observation" in text)
            self.assertTrue(
                "if: always() && steps.backend.outcome != 'skipped'" in text
            )
            self.assertTrue("timeout-minutes: 32" in text)
            self.assertNotIn("clearCache=clear", text)


class HttpTests(unittest.TestCase):
    def response(self, body=None):
        result = Mock()
        result.status = 200
        result.headers = {}
        result.read.return_value = json.dumps(body or {}).encode()
        result.__enter__ = Mock(return_value=result)
        result.__exit__ = Mock(return_value=False)
        return result

    def client(self, opener, *, observe=True):
        return d.Render(
            d.TARGETS["Staging"][0],
            "synthetic-private-token",
            deadline=time.monotonic() + 10,
            request_timeout=1,
            observe_only=observe,
            opener=opener,
        )

    def test_bounded_rate_limit_read_recovery_and_auth_errors(self):
        opener = Mock()
        failure = urllib.error.HTTPError(
            "https://synthetic.invalid",
            429,
            "private-marker",
            {"Retry-After": "1"},
            None,
        )
        opener.open.side_effect = [failure, self.response({"ok": True})]
        client = self.client(opener)
        client.sleep = Mock()
        self.assertEqual(client.call(""), {"ok": True})
        self.assertEqual(opener.open.call_count, 2)
        client.sleep.assert_called_once_with(1)
        for status, code in [
            (401, "AUTHENTICATION_DENIED"),
            (403, "PERMISSION_DENIED"),
            (429, "RATE_LIMITED"),
        ]:
            opener = Mock()
            opener.open.side_effect = urllib.error.HTTPError(
                "https://synthetic.invalid", status, "private-marker", {}, None
            )
            client = self.client(opener)
            client.sleep = Mock()
            with self.assertRaises(d.DeploymentError) as caught:
                client.call("")
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("private-marker", str(caught.exception))
            self.assertLessEqual(opener.open.call_count, 3)

    def test_post_rate_limit_has_no_retry_and_observe_transport_refuses_posts(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://synthetic.invalid", 429, "private-marker", {}, None
        )
        with self.assertRaises(d.DeploymentError):
            self.client(opener, observe=False).call("/deploys", {"commitId": SHA})
        self.assertEqual(opener.open.call_count, 1)
        opener.reset_mock()
        with self.assertRaises(d.DeploymentError):
            self.client(opener).call("/deploys", {"commitId": SHA})
        opener.open.assert_not_called()

    def test_slow_trickling_body_is_bounded_as_a_whole_request(self):
        response = self.response()
        response.read.side_effect = lambda *_: (time.sleep(0.4), b"{}")[1]
        opener = Mock()
        opener.open.return_value = response
        client = self.client(opener)
        client.request_timeout = 0.04
        start = time.monotonic()
        with self.assertRaises(d.DeploymentError):
            client.call("")
        self.assertLess(time.monotonic() - start, 0.3)

    def test_unknown_endpoint_redirect_and_unbounded_reply_refuse(self):
        opener = Mock()
        with self.assertRaises(d.DeploymentError):
            self.client(opener).call("/cancel")
        opener.open.assert_not_called()
        response = self.response()
        response.read.return_value = b"x" * (d.LIMIT + 1)
        opener.open.return_value = response
        with self.assertRaises(d.DeploymentError):
            self.client(opener).call("")
        self.assertIsNone(
            d.NoRedirect().redirect_request(None, None, None, None, None, None)
        )


if __name__ == "__main__":
    unittest.main()
