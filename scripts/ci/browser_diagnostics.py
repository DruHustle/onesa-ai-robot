"""Retain bounded synthetic CI outcomes without messages, traces or session data."""

import json
import math
import os
import re
import resource
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 16 * 1024 * 1024
PROJECTS = {"chromium", "firefox", "webkit"}
STATUSES = {"passed", "failed", "timedOut", "skipped", "interrupted"}


def category(message):
    if not isinstance(message, str):
        return "unclassified"
    if 'while setting up "page"' in message:
        return "page_fixture_timeout"
    if "has been closed" in message:
        return "browser_or_page_closed"
    if "Timeout" in message or "timeout" in message:
        return "timeout"
    return "unclassified"


def summarize(report):
    rows = []

    def visit(suites, depth=0):
        if depth > 16 or not isinstance(suites, list):
            raise ValueError("Invalid bounded suite structure")
        for suite in suites:
            for spec in suite.get("specs", []):
                filename = str(spec.get("file", "")).replace("\\", "/").split("/")[-1]
                if not re.fullmatch(r"[a-z-]{1,80}\.spec\.mjs", filename):
                    filename = "unknown"
                line = spec.get("line")
                line = line if type(line) is int and 0 < line < 1000000 else None
                for test in spec.get("tests", []):
                    project = test.get("projectName")
                    project = project if project in PROJECTS else "unknown"
                    for result in test.get("results", []):
                        if len(rows) >= 1000:
                            raise ValueError("Outcome limit exceeded")
                        status = result.get("status")
                        status = status if status in STATUSES else "unknown"
                        duration = result.get("duration")
                        duration = (
                            duration
                            if type(duration) in {int, float}
                            and math.isfinite(duration)
                            and 0 <= duration <= 3600000
                            else None
                        )
                        errors = result.get("errors", [])
                        if not isinstance(errors, list) or len(errors) > 100:
                            raise ValueError("Invalid error collection")
                        rows.append(
                            {
                                "project": project,
                                "file": filename,
                                "line": line,
                                "status": status,
                                "duration_ms": duration,
                                "error_categories": sorted(
                                    {
                                        category(error.get("message"))
                                        for error in errors
                                        if isinstance(error, dict)
                                    }
                                ),
                            }
                        )
            visit(suite.get("suites", []), depth + 1)

    if not isinstance(report, dict):
        raise TypeError("Report object required")
    visit(report.get("suites", []))
    return {
        "evidence_kind": "synthetic-browser-diagnostic-only",
        "qualification_or_authorization": False,
        "outcomes": rows,
        "counts": {
            status: sum(r["status"] == status for r in rows)
            for status in sorted(STATUSES)
        },
        "global_error_categories": sorted(
            {
                category(error.get("message"))
                for error in report.get("errors", [])
                if isinstance(error, dict)
            }
        ),
    }


def main(source, target):
    value = {
        "evidence_kind": "synthetic-browser-diagnostic-only",
        "qualification_or_authorization": False,
    }
    try:
        if (
            source.is_symlink()
            or not source.is_file()
            or source.stat().st_size > MAX_BYTES
        ):
            raise ValueError("Report unavailable or outside bound")
        value = summarize(json.loads(source.read_text()))
        value["diagnostic_status"] = "AVAILABLE"
    except (ValueError, TypeError, AttributeError, KeyError, OSError, RecursionError):
        value["diagnostic_status"] = "UNAVAILABLE"
    value["at"] = datetime.now(timezone.utc).isoformat()
    sha = os.environ.get("GITHUB_SHA", "")
    value["source"] = sha if re.fullmatch(r"[a-f0-9]{40}", sha) else None
    value["observer_max_rss_native_units"] = resource.getrusage(
        resource.RUSAGE_SELF
    ).ru_maxrss
    value["observer_platform"] = sys.platform
    with target.open("x") as output:
        json.dump(value, output, indent=2)
    target.chmod(0o600)
    print("Synthetic browser diagnostic: " + value["diagnostic_status"])


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
