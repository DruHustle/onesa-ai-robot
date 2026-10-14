"""Staging lease transfer must preserve history, credentials and production authority."""

import os
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import journal_handoff as handoff
from evidence import REPOSITORY, Rejected
from staging_configuration import SERVICE


class HandoffTests(unittest.TestCase):
    def test_running_journal_is_fenced_before_next_deployment_origin_is_saved(self):
        workflow = (
            Path(__file__).resolve().parents[2]
            / ".github/workflows/release-staging.yml"
        ).read_text()
        resolve = workflow.index(
            "run: python3 scripts/release/cloud.py resolve-preview"
        )
        stop = workflow.index("run: python3 scripts/release/journal_handoff.py")
        bind = workflow.index("run: python3 scripts/release/cloud.py bind-preview")
        deploy = workflow.index("python3 scripts/deploy_render.py")
        self.assertLess(resolve, stop)
        self.assertLess(stop, bind)
        self.assertLess(bind, deploy)

    def test_operator_failures_report_only_fixed_phase_and_status(self):
        sentinel = "synthetic-private-provider-body"
        for status in [401, 403, 503]:
            failure = urllib.error.HTTPError(
                "https://synthetic.invalid/" + sentinel, status, sentinel, {}, None
            )
            with patch("journal_handoff.urllib.request.build_opener") as factory:
                factory.return_value.open.side_effect = failure
                with self.assertRaises(handoff.HandoffRequestFailure) as caught:
                    handoff.read_api(
                        factory.return_value,
                        urllib.request.Request("https://synthetic.invalid"),
                        "/api/v1/auth/login",
                    )
                self.assertEqual(caught.exception.phase, "operator-login")
                self.assertEqual(caught.exception.status, status)
                self.assertNotIn(sentinel, str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)

    def context(self):
        return {
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_REF": "refs/heads/staging",
            "GITHUB_ACTOR": "DruHustle",
            "GITHUB_TRIGGERING_ACTOR": "DruHustle",
            "RUNNER_ENVIRONMENT": "github-hosted",
            "RENDER_SERVICE_ID": SERVICE,
        }

    def test_production_untrusted_actor_runner_and_foreign_resource_fail_before_access(
        self,
    ):
        for change in [
            {"GITHUB_REF": "refs/heads/main"},
            {"GITHUB_ACTOR": "foreign"},
            {"GITHUB_TRIGGERING_ACTOR": "foreign"},
            {"RUNNER_ENVIRONMENT": "self-hosted"},
            {"RENDER_SERVICE_ID": "srv-production"},
            {"GITHUB_REPOSITORY": "foreign/robot"},
        ]:
            with (
                patch.dict(os.environ, {**self.context(), **change}, clear=True),
                patch.object(handoff, "provider") as provider,
                self.assertRaises(Rejected),
            ):
                handoff.handoff()
            provider.assert_not_called()

    def test_only_the_observed_lease_is_expired_without_removing_history_or_owner(self):
        owner = "a" * 32
        calls = []

        def execute(token, sql, args=()):
            self.assertEqual(token, "synthetic-private-token")
            calls.append((sql, args))
            if sql.startswith("UPDATE "):
                self.assertEqual(args, (owner,))
                return [{"owner": owner}]
            return [{"owner": owner, "active": 1 if len(calls) == 1 else 0}]

        handoff.fence_stopped_lease("synthetic-private-token", execute)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(handoff.LEASE in sql for sql, _ in calls))
        self.assertFalse(
            any(
                word in sql
                for sql, _ in calls
                for word in [
                    "DELETE",
                    "DROP",
                    "TRUNCATE",
                    "tasks",
                    "password",
                    "SET owner",
                ]
            )
        )

    def test_a_concurrent_owner_change_is_never_overwritten_or_accepted(self):
        results = [[{"owner": "a" * 32, "active": 1}], []]
        with self.assertRaises(Rejected):
            handoff.fence_stopped_lease("synthetic", lambda *_: results.pop(0))

    def test_an_already_expired_lease_requires_no_database_write(self):
        calls = []

        def execute(_token, sql, _args=()):
            calls.append(sql)
            return [{"owner": "a" * 32, "active": 0}]

        handoff.fence_stopped_lease("synthetic", execute)
        self.assertTrue(all(sql.startswith("SELECT ") for sql in calls))

    def exercise_handoff(self, status, history, pending=0, rechecked=None, after=None):
        service = {
            "id": SERVICE,
            "repo": "https://github.com/" + REPOSITORY,
            "branch": "staging",
            "autoDeployTrigger": "off",
            "type": "web_service",
            "serviceDetails": {
                "plan": "free",
                "region": "frankfurt",
                "url": handoff.API,
            },
        }
        settings = {
            "ROBOT_DEPLOYMENT_ENVIRONMENT": "staging",
            "ROBOT_ACTUATION_ENABLED": "false",
            "ROBOT_STORAGE_MODE": "turso",
            "ROBOT_TURSO_DATABASE_URL": handoff.TURSO,
            "ROBOT_TURSO_AUTH_TOKEN": "synthetic-private-token",
            "ROBOT_PUBLIC_ORIGIN": "https://synthetic.vercel.app",
            "ROBOT_OPERATOR_NAME": "operator",
        }
        calls = []
        stopped = False
        status_reads = 0
        queries = []

        def read(_opener, request, route):
            nonlocal stopped, status_reads
            calls.append((route, request.get_method()))
            if route == "/api/v1/auth/login":
                return {"csrf": "synthetic-csrf"}
            if route == "/api/v1/auth/logout":
                return {"status": "signed_out"}
            if route == "/api/v1/stop":
                stopped = True
                return {"status": "stopped"}
            if route == "/api/v1/tasks":
                return {"tasks": after if stopped and after is not None else history}
            if route == "/api/v1/status":
                status_reads += 1
                if stopped:
                    return {**status, "stopped": True}
                return (
                    rechecked if status_reads > 1 and rechecked is not None else status
                )
            self.fail("Unexpected handoff request")

        def sql(token, statement, args=()):
            self.assertEqual(token, "synthetic-private-token")
            self.assertEqual(args, ())
            queries.append(statement)
            return [{"pending": pending}]

        failure = None
        result = None
        with (
            patch.dict(
                os.environ,
                {
                    **self.context(),
                    "ROBOT_TEST_PASSWORD": "synthetic-private-password",
                    "ROBOT_TEST_OPERATOR": "operator",
                },
                clear=True,
            ),
            patch.object(
                handoff,
                "provider",
                side_effect=[
                    service,
                    [{"envVar": {"key": k, "value": v}} for k, v in settings.items()],
                ],
            ),
            patch.object(handoff, "read_api", side_effect=read),
            patch.object(handoff, "sql_call", side_effect=sql),
            patch.object(handoff, "fence_stopped_lease") as expire,
        ):
            try:
                result = handoff.handoff()
            except Rejected as error:
                failure = str(error)
        return result, failure, calls, queries, expire.call_count

    def idle(self):
        return {
            "mode": "simulation",
            "physical_actuation": False,
            "stopped": False,
            "active_task": None,
        }

    def test_active_or_unsafe_runtime_fails_before_stop_or_lease_access(self):
        for change in [
            {"mode": "physical"},
            {"physical_actuation": True},
            {"active_task": "existing-active-task"},
            {"stopped": None},
        ]:
            with self.subTest(change=change):
                result, failure, calls, queries, fences = self.exercise_handoff(
                    {**self.idle(), **change}, []
                )
                self.assertIsNone(result)
                self.assertIn("preserve existing work", failure)
                self.assertNotIn(("/api/v1/stop", "POST"), calls)
                self.assertEqual(queries, [])
                self.assertEqual(fences, 0)
                self.assertIn(("/api/v1/auth/logout", "POST"), calls)

    def test_proposed_running_and_hidden_pending_history_are_preserved(self):
        for history, pending in [
            ([{"id": "existing-proposal", "state": "proposed"}], 0),
            ([{"id": "existing-running", "state": "running"}], 0),
            ([{"id": "recent-completed", "state": "completed"}], 1),
        ]:
            with self.subTest(history=history, pending=pending):
                result, failure, calls, queries, fences = self.exercise_handoff(
                    self.idle(), history, pending
                )
                self.assertIsNone(result)
                self.assertIn("preserv", failure)
                self.assertNotIn(("/api/v1/stop", "POST"), calls)
                self.assertEqual(fences, 0)
                self.assertTrue(all(query.startswith("SELECT ") for query in queries))
                self.assertTrue(
                    all(
                        route in {"/api/v1/auth/login", "/api/v1/auth/logout"}
                        for route, method in calls
                        if method == "POST"
                    )
                )

    def test_a_new_active_task_during_idle_readback_is_never_stopped(self):
        result, failure, calls, queries, fences = self.exercise_handoff(
            self.idle(),
            [],
            rechecked={**self.idle(), "active_task": "new-existing-task"},
        )
        self.assertIsNone(result)
        self.assertIn("preserve existing work", failure)
        self.assertNotIn(("/api/v1/stop", "POST"), calls)
        self.assertEqual(fences, 0)
        self.assertEqual(len(queries), 1)

    def test_idle_unlatched_history_is_unchanged_before_the_lease_is_fenced(self):
        history = [
            {
                "id": "existing-completed",
                "state": "completed",
                "reason": "target_reached",
            }
        ]
        result, failure, calls, queries, fences = self.exercise_handoff(
            self.idle(), history
        )
        self.assertIsNone(failure)
        self.assertTrue(result["history_preserved"])
        self.assertEqual(fences, 1)
        self.assertEqual(calls.count(("/api/v1/stop", "POST")), 1)
        self.assertGreater(
            calls.index(("/api/v1/stop", "POST")), calls.index(("/api/v1/tasks", "GET"))
        )
        self.assertEqual(
            queries,
            [
                "SELECT count(*) AS pending FROM robot_simulation_tasks_v1 WHERE state IN ('running','proposed')"
            ],
        )

    def test_changed_history_cannot_be_fenced_or_rewritten_to_pass(self):
        history = [{"id": "existing-completed", "state": "completed"}]
        result, failure, calls, queries, fences = self.exercise_handoff(
            self.idle(), history, after=[{"id": "unexpected", "state": "cancelled"}]
        )
        self.assertIsNone(result)
        self.assertIn("history changed", failure)
        self.assertEqual(fences, 0)
        self.assertTrue(all(query.startswith("SELECT ") for query in queries))
        self.assertIn(("/api/v1/auth/logout", "POST"), calls)


if __name__ == "__main__":
    unittest.main()
