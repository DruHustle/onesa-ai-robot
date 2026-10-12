"""Version and digest simulation-only edge packages; never install them."""

import hashlib
import json
import os
import sys
from pathlib import Path

folder = Path(sys.argv[1])
preflight = json.loads((folder / "preflight" / "record.json").read_text())
files = {
    name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
    for name in ["simulator.tar", "interfaces.tar"]
}
record = {
    "schema_version": 1,
    "repository": os.environ["GITHUB_REPOSITORY"],
    "candidate_commit": os.environ["GITHUB_SHA"],
    "version": "0.1.0+" + os.environ["GITHUB_SHA"][:12],
    "workflow_run_id": int(os.environ["GITHUB_RUN_ID"]),
    "source_sha256": preflight["valid_for_source_sha256"],
    "sha256": files,
    "scope": "edge-software-simulation-only",
    "ros_target": "Jazzy/Linux",
    "SIMULATION_VERIFIED": preflight["SIMULATION_VERIFIED"],
    "ROBOT_SAFETY_SOFTWARE_VERIFIED": preflight["ROBOT_SAFETY_SOFTWARE_VERIFIED"],
    "ROS2_INTERFACE_VERIFIED": preflight["ROS2_INTERFACE_VERIFIED"],
    "EDGE_DEPLOYMENT_VERIFIED": "NOT TESTED",
    "PHYSICAL_HARDWARE_APPROVED": "BLOCKED",
    "distribution": "owner-approved exact-candidate simulation artifact; no registry or hardware deployment",
    "licensing_review": "approved by owner workflow dispatch",
}
(folder / "record.json").write_text(json.dumps(record, indent=2) + "\n")
