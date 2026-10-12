"""Reject API/client drift without adopting a new compatibility baseline."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paths = [
    root / "onesa-ai-robot-frontend/contracts/openapi.json",
    root / "onesa-ai-robot-frontend/contracts/schema.ts",
]
before = {p: p.read_bytes() for p in paths}
subprocess.run(
    [sys.executable, str(root / "scripts/generate-contracts.py")], check=True
)
subprocess.run(
    [
        "node",
        "node_modules/openapi-typescript/bin/cli.js",
        "contracts/openapi.json",
        "-o",
        "contracts/schema.ts",
    ],
    cwd=root / "onesa-ai-robot-frontend",
    check=True,
)
if any(p.read_bytes() != before[p] for p in paths):
    raise SystemExit(
        "API/client drift detected: review and regenerate the changed contract explicitly"
    )
print("Simulation API and generated types match the source contract.")
