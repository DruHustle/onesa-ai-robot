"""Staging lease transfer must preserve history, credentials and production authority."""

import json
import os
import unittest
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

    def test_active_or_physical_simulation_cannot_expire_the_lease(self):
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

        class Response:
            status = 200

            def __init__(self, value):
                self.value = value

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def read(self, _limit):
                return json.dumps(self.value).encode()

        for invalid in [
            {"stopped": False},
            {"physical_actuation": True},
            {"active_task": "running-synthetic-task"},
        ]:
            status = {
                "mode": "simulation",
                "physical_actuation": False,
                "stopped": True,
                "active_task": None,
                **invalid,
            }
            results = [
                Response({"csrf": "synthetic-csrf"}),
                Response({"status": "stopped"}),
                Response(status),
                Response({"status": "signed_out"}),
            ]
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
                        [
                            {"envVar": {"key": k, "value": v}}
                            for k, v in settings.items()
                        ],
                    ],
                ),
                patch.object(handoff.urllib.request, "build_opener") as opener,
                patch.object(handoff, "fence_stopped_lease") as expire,
                self.assertRaises(Rejected),
            ):
                opener.return_value.open.side_effect = results
                handoff.handoff()
            expire.assert_not_called()


if __name__ == "__main__":
    unittest.main()
