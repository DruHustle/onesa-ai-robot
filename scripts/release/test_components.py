"""Retained-component provenance failures use synthetic GitHub/provider data only."""

import copy
import hashlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import cloud
import components as c
import evidence as e
import free_gate as f
from test_evidence import FINGERPRINT, SHA
from test_free_gate import GitHub as ExistingGitHub

NEW = "f" * 40


class GitHub(ExistingGitHub):
    def __init__(self):
        super().__init__()
        self.entries = [
            {
                "path": path,
                "type": "tree"
                if path in {"onesa-ai-robot-backend", "ros2", "edge"}
                else "blob",
                "mode": "040000"
                if path in {"onesa-ai-robot-backend", "ros2", "edge"}
                else "100644",
                "sha": hashlib.sha1(path.encode()).hexdigest(),
            }
            for path in c.IDENTITY_PATHS
        ]
        self.changed = None
        self.compare = {"status": "ahead", "behind_by": 0}
        self.truncated = False
        with patch.object(e, "source_hash", return_value=FINGERPRINT):
            self.record = f.qualification(self, SHA, self.run(30), 20)
            self.approval = f.authorize(
                self, SHA, self.run(40), 30, e.digest(self.record), None, "approve"
            )

    def api(self, path, pages=False):
        if "/git/trees/" in path:
            entries = copy.deepcopy(self.entries)
            if self.changed and NEW in path:
                next(item for item in entries if item["path"] == self.changed)[
                    "sha"
                ] = "0" * 40
            return {"tree": entries, "truncated": self.truncated}
        if "/compare/" in path:
            return self.compare
        return super().api(path, pages=pages)


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.github = GitHub()

    def test_reuse_records_actual_new_frontend_and_old_backend_provenance(self):
        result = c.plan(self.github, NEW, 40)
        self.assertEqual(result["frontend_commit"], NEW)
        self.assertEqual(result["backend_commit"], SHA)
        self.assertEqual(result["baseline"]["authorization"]["run_id"], 40)
        self.assertEqual(result["baseline"]["qualification"]["run_id"], 30)
        self.assertEqual(
            result["baseline"]["tested_build"]["application"], e.PRODUCT + "-backend"
        )
        self.assertFalse(result["physical_hardware_authorized"])
        self.assertEqual(c.verify(self.github, NEW, result), result)

    def test_backend_runtime_or_any_contract_drift_rejects(self):
        for path in c.IDENTITY_PATHS:
            with self.subTest(path=path), self.assertRaises(e.Rejected):
                self.github.changed = path
                c.plan(self.github, NEW, 40)

    def test_reuse_fails_for_changed_approval_qualification_or_artifact(self):
        for field, value in [
            ("candidate_commit", NEW),
            ("approver", "outsider"),
            ("decision", "revoke"),
            ("physical_hardware_authorized", True),
            ("evidence_sha256", "0" * 64),
            ("repository", "foreign/repository"),
        ]:
            github = GitHub()
            github.approval[field] = value
            with self.subTest(field=field), self.assertRaises(e.Rejected):
                c.plan(github, NEW, 40)

    def test_stale_superseded_pending_or_rerun_baseline_rejects(self):
        cases = [
            "stale",
            "superseded",
            "pending",
            "rerun",
            "foreign",
            "actor",
            "ref",
            "event",
        ]
        for case in cases:
            github = GitHub()
            run = github.run(40)
            if case == "stale":
                github.approval["approved_at"] = (
                    datetime.now(timezone.utc) - timedelta(hours=25)
                ).isoformat()
            if case == "superseded":
                github.latest = 41
                github.runs_by_id[41] = {**run, "id": 41}
            if case == "pending":
                run["status"] = "in_progress"
            if case == "rerun":
                run["run_attempt"] = 2
            if case == "foreign":
                run["head_repository"]["full_name"] = "foreign/repository"
            if case == "actor":
                run["actor"]["login"] = "outsider"
            if case == "ref":
                run["head_branch"] = "dependabot/security-fixture"
            if case == "event":
                run["event"] = "pull_request"
            with self.subTest(case=case), self.assertRaises(e.Rejected):
                c.plan(github, NEW, 40)

    def test_incomplete_tree_diverged_source_or_failed_prior_ci_rejects(self):
        for case in ["truncated", "missing", "symlink", "diverged", "ci"]:
            github = GitHub()
            if case == "truncated":
                github.truncated = True
            if case == "missing":
                github.entries.pop()
            if case == "symlink":
                github.entries[0]["mode"] = "120000"
            if case == "diverged":
                github.compare = {"status": "diverged", "behind_by": 1}
            if case == "ci":
                github.ci_jobs[0]["conclusion"] = "failure"
            with self.subTest(case=case), self.assertRaises(e.Rejected):
                c.plan(github, NEW, 40)

    def test_caller_cannot_forge_component_plan_or_substitute_candidate_sha(self):
        valid = c.plan(self.github, NEW, 40)
        for field, value in [
            ("backend_commit", NEW),
            ("frontend_commit", SHA),
            ("backend_identity_sha256", "0" * 64),
            ("physical_hardware_authorized", True),
            ("production_backend_action", "redeploy-arbitrary-source"),
        ]:
            selected = {**valid, field: value}
            with self.subTest(field=field), self.assertRaises(e.Rejected):
                c.verify(self.github, NEW, selected)

    def test_retained_provider_must_be_latest_live_exact_source_and_safe_ready(self):
        service = {
            "repo": "https://github.com/" + e.REPOSITORY,
            "rootDir": "onesa-ai-robot-backend",
            "serviceDetails": {"url": "https://synthetic.onrender.com"},
        }
        deployment = {"id": "dep-synthetic", "status": "live", "commit": {"id": SHA}}
        ready = {
            "status": "ready",
            "mode": "simulation",
            "physical_actuation": False,
            "deployment_environment": "production",
        }
        with (
            patch.dict(
                os.environ,
                {
                    "RENDER_SERVICE_ID": "srv-synthetic",
                    "RENDER_API_KEY": "synthetic-test-only",
                },
                clear=True,
            ),
            patch.object(cloud, "preflight"),
            patch.object(
                cloud, "provider", side_effect=[service, [], [{"deploy": deployment}]]
            ),
            patch("smoke.wait_readiness", return_value=ready),
        ):
            result = cloud.inspect_backend("Production", SHA)
            self.assertEqual(result["commit"], SHA)
            self.assertEqual(result["readiness"], "PASS")
            self.assertNotIn("synthetic-test-only", str(result))
        for changed, state in [
            ({**deployment, "commit": {"id": NEW}}, ready),
            ({**deployment, "status": "build_in_progress"}, ready),
            (deployment, {**ready, "physical_actuation": True}),
            (deployment, {**ready, "deployment_environment": "staging"}),
        ]:
            with (
                self.subTest(state=state),
                patch.dict(
                    os.environ,
                    {
                        "RENDER_SERVICE_ID": "srv-synthetic",
                        "RENDER_API_KEY": "synthetic-test-only",
                    },
                    clear=True,
                ),
                patch.object(cloud, "preflight"),
                patch.object(
                    cloud, "provider", side_effect=[service, [], [{"deploy": changed}]]
                ),
                patch("smoke.wait_readiness", return_value=state),
                self.assertRaises(e.Rejected),
            ):
                cloud.inspect_backend("Production", SHA)

    def test_private_runtime_digest_changes_when_credentials_or_layout_change(self):
        service = {
            "repo": "https://github.com/" + e.REPOSITORY,
            "serviceDetails": {"url": "https://synthetic.onrender.com"},
        }
        latest = [
            {"deploy": {"id": "dep-synthetic", "status": "live", "commit": {"id": SHA}}}
        ]
        ready = {
            "status": "ready",
            "mode": "simulation",
            "physical_actuation": False,
            "deployment_environment": "production",
        }
        observations = []
        for token in ["synthetic-original", "synthetic-changed"]:
            with (
                patch.dict(
                    os.environ,
                    {
                        "RENDER_SERVICE_ID": "srv-synthetic",
                        "RENDER_API_KEY": "synthetic-only",
                    },
                    clear=True,
                ),
                patch.object(cloud, "preflight"),
                patch.object(
                    cloud,
                    "provider",
                    side_effect=[
                        service,
                        [{"envVar": {"key": "ROBOT_TURSO_AUTH_TOKEN", "value": token}}],
                        latest,
                    ],
                ),
                patch("smoke.wait_readiness", return_value=ready),
            ):
                observations.append(cloud.inspect_backend("Production", SHA))
        self.assertNotEqual(
            observations[0]["private_context_sha256"],
            observations[1]["private_context_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
