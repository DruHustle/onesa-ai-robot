"""Synthetic diagnostic fields never copy error bodies or grant a release."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from browser_diagnostics import main, summarize


class DiagnosticTests(unittest.TestCase):
    def report(self):
        return {
            "suites": [
                {
                    "specs": [
                        {
                            "file": "/runner/administration.spec.mjs",
                            "line": 27,
                            "title": "private-title-canary",
                            "tests": [
                                {
                                    "projectName": "webkit",
                                    "results": [
                                        {
                                            "status": "timedOut",
                                            "duration": 30000,
                                            "stdout": ["private-output-canary"],
                                            "errors": [
                                                {
                                                    "message": 'Test timeout while setting up "page". private-secret-canary',
                                                    "stack": "private-stack-canary",
                                                }
                                            ],
                                            "attachments": [
                                                {"body": "private-body-canary"}
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ]
        }

    def test_page_setup_failure_and_counts_preserved_without_private_fields(self):
        result = summarize(self.report())
        self.assertEqual(result["counts"]["timedOut"], 1)
        self.assertEqual(
            result["outcomes"][0]["error_categories"], ["page_fixture_timeout"]
        )
        self.assertFalse(result["qualification_or_authorization"])
        self.assertNotIn("private-", json.dumps(result))

    def test_passed_failed_and_skipped_remain_distinct(self):
        for status in ["passed", "failed", "skipped", "interrupted"]:
            report = self.report()
            report["suites"][0]["specs"][0]["tests"][0]["results"][0]["status"] = status
            self.assertEqual(summarize(report)["counts"][status], 1)

    def test_unknown_identifiers_and_nonfinite_duration_are_not_copied(self):
        report = self.report()
        spec = report["suites"][0]["specs"][0]
        spec.update(file="private-secret-canary", line=True)
        test = spec["tests"][0]
        test["projectName"] = "private-project-canary"
        test["results"][0]["duration"] = float("nan")
        result = summarize(report)["outcomes"][0]
        self.assertEqual(result["file"], "unknown")
        self.assertEqual(result["project"], "unknown")
        self.assertIsNone(result["line"])
        self.assertIsNone(result["duration_ms"])

    def test_output_bound_and_nesting_fail_closed(self):
        report = self.report()
        spec = report["suites"][0]["specs"][0]
        spec["tests"][0]["results"] *= 1001
        with self.assertRaises(ValueError):
            summarize(report)
        nested = []
        for _ in range(18):
            nested = [{"suites": nested}]
        with self.assertRaises(ValueError):
            summarize({"suites": nested})

    def test_missing_and_malformed_report_remain_unavailable_and_never_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for index, content in enumerate([None, "malformed", "[]"]):
                source, target = base / f"source{index}", base / f"target{index}"
                if content is not None:
                    source.write_text(content)
                main(source, target)
                result = json.loads(target.read_text())
                self.assertEqual(result["diagnostic_status"], "UNAVAILABLE")
                self.assertFalse(result["qualification_or_authorization"])
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_oversized_report_is_not_parsed_or_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "source", Path(directory) / "target"
            source.write_text(json.dumps(self.report()))
            with patch("browser_diagnostics.MAX_BYTES", 1):
                main(source, target)
            result = json.loads(target.read_text())
            self.assertEqual(result["diagnostic_status"], "UNAVAILABLE")
            self.assertNotIn("private-", target.read_text())

    def test_symlink_source_is_not_read(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            real, source, target = base / "real", base / "source", base / "target"
            real.write_text("private-source-canary")
            source.symlink_to(real)
            main(source, target)
            self.assertEqual(
                json.loads(target.read_text())["diagnostic_status"], "UNAVAILABLE"
            )
            self.assertNotIn("private-", target.read_text())

    def test_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "missing", Path(directory) / "target"
            target.write_text("old-evidence")
            with self.assertRaises(FileExistsError):
                main(source, target)
            self.assertEqual(target.read_text(), "old-evidence")


if __name__ == "__main__":
    unittest.main()
