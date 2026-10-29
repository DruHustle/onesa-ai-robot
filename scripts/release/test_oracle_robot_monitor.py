"""Bounded real-monitor recovery semantics; no hosted qualification claims."""

import copy
import datetime as dt
import unittest
from unittest.mock import patch

import oracle_robot as r


class PostStagingMonitorTests(unittest.TestCase):
    def setUp(self):
        self.current = dt.datetime(2026, 10, 29, 10, 8, 10, tzinfo=dt.timezone.utc)
        self.stage = {"observed_at": self.current.isoformat()}
        self.elapsed = 0
        self.healthy = {
            "checked_at": self.current.isoformat(),
            "simulation": False,
            "alerts": [],
            "healthy_samples": 2,
            "incident_open": False,
            "notification_reconciliation_required": False,
            "metrics": {},
        }

    def sleep(self, seconds):
        self.elapsed += seconds

    def call(self, samples):
        with (
            patch.object(r, "read", side_effect=samples),
            patch.object(
                r,
                "now",
                side_effect=lambda: self.current + dt.timedelta(seconds=self.elapsed),
            ),
            patch.object(r.time, "monotonic", side_effect=lambda: self.elapsed),
            patch.object(r.time, "sleep", side_effect=self.sleep),
        ):
            return r.post_staging_monitor(self.stage)

    def test_actual_staging_interruption_waits_for_observed_recovery(self):
        failed = {
            **self.healthy,
            "alerts": ["backend-api-unavailable"],
            "healthy_samples": 0,
            "incident_open": True,
        }
        fresh = {
            **self.healthy,
            "checked_at": (self.current + dt.timedelta(seconds=5)).isoformat(),
        }
        self.assertEqual(self.call([failed, fresh]), fresh)
        self.assertEqual(self.elapsed, 5)
        self.assertEqual(failed["alerts"], ["backend-api-unavailable"])

    def test_healthy_pre_staging_sample_cannot_qualify(self):
        stale = {
            **self.healthy,
            "checked_at": (self.current - dt.timedelta(seconds=1)).isoformat(),
        }
        self.assertEqual(self.call([stale, self.healthy]), self.healthy)
        self.assertEqual(self.elapsed, 5)

    def test_unresolved_failure_exhausts_bounded_wait_without_success(self):
        failed = {**self.healthy, "alerts": ["database-unavailable"]}
        with self.assertRaisesRegex(r.Refused, "POST_STAGING_MONITOR_NOT_RECOVERED"):
            self.call(lambda *_: failed)
        self.assertEqual(self.elapsed, 240)

    def test_pending_notification_reconciliation_and_incident_still_block(self):
        for field, value in [
            ("notification_pending", {"reference": "fixture"}),
            ("notification_reconciliation_required", True),
            ("incident_open", True),
            ("healthy_samples", 1),
            ("healthy_samples", True),
        ]:
            with self.subTest(field=field, value=value):
                self.elapsed = 0
                failed = {**self.healthy, field: value}
                with self.assertRaisesRegex(
                    r.Refused, "POST_STAGING_MONITOR_NOT_RECOVERED"
                ):
                    self.call(lambda *_, sample=failed: sample)

    def test_simulated_future_and_naive_samples_fail_immediately(self):
        for change in [
            {"simulation": True},
            {"checked_at": (self.current + dt.timedelta(seconds=1)).isoformat()},
            {"checked_at": self.current.replace(tzinfo=None).isoformat()},
        ]:
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(r.Refused, "GENUINE_MONITOR_SAMPLE_REQUIRED"),
            ):
                self.call([{**self.healthy, **change}])
        self.assertEqual(self.elapsed, 0)

    def test_missing_or_malformed_monitor_data_never_defaults_to_success(self):
        for sample in [{}, {**self.healthy, "checked_at": "invalid"}]:
            with self.subTest(sample=sample), self.assertRaises((KeyError, ValueError)):
                self.call([sample])

    def test_stale_or_future_stage_is_refused_before_monitor_read(self):
        for offset in [-301, 1]:
            self.stage["observed_at"] = (
                self.current + dt.timedelta(seconds=offset)
            ).isoformat()
            with (
                self.subTest(offset=offset),
                self.assertRaisesRegex(r.Refused, "FRESH_STAGING_RECEIPT_REQUIRED"),
            ):
                self.call([])

    def test_no_monitor_record_or_failed_sample_is_rewritten(self):
        original = copy.deepcopy(self.healthy)
        self.assertEqual(self.call([self.healthy]), original)
        self.assertEqual(self.healthy, original)

    def test_stage_expiry_during_wait_cannot_extend_qualification_freshness(self):
        self.stage["observed_at"] = (
            self.current - dt.timedelta(seconds=299)
        ).isoformat()
        failed = {**self.healthy, "alerts": ["backend-api-unavailable"]}
        with self.assertRaisesRegex(r.Refused, "FRESH_STAGING_RECEIPT_REQUIRED"):
            self.call([failed, self.healthy])
        self.assertEqual(self.elapsed, 5)


if __name__ == "__main__":
    unittest.main()
