"""Pass verified staging-only device identity privately between release steps."""

import json
import os
import re
from pathlib import Path

from evidence import REPOSITORY, require


def path():
    return Path(
        os.environ["RUNNER_TEMP"], "robot-release", "verified-edge-fixture.json"
    )


def remember(values):
    if not os.environ.get("RUNNER_TEMP"):
        return
    require(
        os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
        and os.environ.get("GITHUB_REF") == "refs/heads/staging",
        "Private edge fixture staging context required",
    )
    device = values.get("ROBOT_EDGE_DEVICE_ID", "")
    require(
        re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", device) is not None,
        "Configured staging device identity required",
    )
    record = {
        "repository": REPOSITORY,
        "scope": "approved-synthetic-staging",
        "candidate_commit": os.environ["GITHUB_SHA"],
        "device_id": device,
    }
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.exists():
        require(
            file.stat().st_mode & 0o077 == 0,
            "Private edge fixture permissions required",
        )
        require(
            json.loads(file.read_text()) == record,
            "Private edge fixture binding changed",
        )
        return
    descriptor = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(record, handle)


def restore(environment):
    if environment != "Staging" or os.environ.get("ROBOT_EDGE_DEVICE_ID"):
        return
    file = path()
    require(
        file.is_file() and file.stat().st_mode & 0o077 == 0,
        "Private edge fixture required",
    )
    record = json.loads(file.read_text())
    require(
        record.get("repository") == REPOSITORY
        and record.get("scope") == "approved-synthetic-staging"
        and record.get("candidate_commit") == os.environ["GITHUB_SHA"],
        "Private edge fixture candidate mismatch",
    )
    require(
        re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", record.get("device_id", "")) is not None,
        "Private edge fixture identity invalid",
    )
    os.environ["ROBOT_EDGE_DEVICE_ID"] = record["device_id"]
