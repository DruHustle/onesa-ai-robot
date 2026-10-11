"""Path-aware feature CI; main/dispatch always produce complete release evidence."""

import json
import os
import subprocess

full = (
    os.environ.get("GITHUB_REF") == "refs/heads/main"
    or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
)
base = os.environ.get("BASE_SHA", "")
if full or not base or set(base) == {"0"}:
    changed = ["shared"]
else:
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", base, "HEAD"], text=True
    ).splitlines()
shared = any(
    not name.startswith(
        ("onesa-ai-robot-frontend/", "onesa-ai-robot-backend/", "docs/")
    )
    for name in changed
)
# Backend schemas/safety affect the typed client and browser/operator contract.
backend = shared or any(name.startswith("onesa-ai-robot-backend/") for name in changed)
frontend = (
    shared
    or backend
    or any(name.startswith("onesa-ai-robot-frontend/") for name in changed)
)
with open(os.environ["GITHUB_OUTPUT"], "a") as output:
    output.write(
        "applications="
        + json.dumps(
            [
                name
                for name, enabled in [("frontend", frontend), ("backend", backend)]
                if enabled
            ]
            or ["frontend"]
        )
        + "\n"
    )
    output.writelines(
        f"{name}={str(enabled).lower()}\n"
        for name, enabled in [
            ("backend", backend),
            ("frontend", frontend),
            ("edge", backend or any(name.startswith("ros2/") for name in changed)),
        ]
    )
