# Start Here — Onesa Robot Engineering

Audience/classification: authorized engineers / INTERNAL. Owner: Robot engineering.
Version: 1.0; reviewed 2026-10-14. Scope: cloud software simulation, with separately
qualified edge adapters. This is not permission to operate physical hardware.

## Day 1 — Product and access

Read the root README, AGENTS, [simulation architecture](SIMULATION_ARCHITECTURE.md)
and [ROS scope](../../ros2/README.md). Identify the public product at `/` and operator
console at `/console`. Private payloads require the backend's operator session even
when a frontend preview is already protected by its provider. Product authentication,
deployment environment and simulation state are separate dimensions.

Checkpoint: explain why an AI account, device bearer token and browser appearance
cannot grant Robot control. Request engineering/hosting access through the current
owner; new team membership does not automatically widen Cloudflare Access or operator
permissions. No production credentials are required for local learning.

## Day 2 — Isolated simulator

Follow both component READMEs with Node 24 and Python 3.11. Install locked dependencies,
use ignored local configuration and synthetic credentials, and start a private local
SQLite simulator. Run the [command matrix](BUILD_AND_TEST.md), reset the stop state,
propose/approve a safe synthetic movement, then cancel and sign out.

Checkpoint: show anonymous status denial, preserved task history after restart,
revoked sessions and latched stop. Explain the generated backend OpenAPI → TypeScript
client pipeline; change the source schema and run the documented generators when a
contract changes. No build imports an unversioned sibling checkout.

## Day 3 — Contribution and release

Use only **dev → staging → main**. Read [release qualification](AUTOMATED_QUALIFICATION.md),
[deployment](DEPLOYMENT.md), [Free safeguards](../development/PRIVATE_FREE_SAFEGUARDS.md)
and actual branch-protection evidence. Preserve concurrent work and stage reviewed
paths. Automated annotations assist review; they are not an independent human verdict.
Automatic dependency branches are disabled; apply reviewed updates on dev while
retaining advisory alerts and security scans.

Checkpoint: identify exact candidate/artifact/schema evidence, owner authorization,
hosted staging checks and rollback boundaries. A source change invalidates affected
acceptance. Never promote by editing PASS flags or reusing another commit's receipt.

## Day 4 — Operations and safety

Read the remote journal lease, stop/freshness/watchdog and recovery procedures. Render
Free has no durable local disk; the selected production Turso journal is a distinct
binding from staging. Backups/restoration/alerts need their own current evidence.
An original PC-to-VM Tailscale administrative tunnel is separate from cloud-edge
Robot telemetry and does not authorize DDS, actuator, camera or control listeners.

Checkpoint: explain network-loss behavior and why stopped tasks never auto-resume.
Distinguish software simulation qualification, ROS message compatibility, model
integration, edge installation and physical safety authorization.

## First engineering contribution

1. Inspect dev, status, worktrees and relevant instructions; preserve unrelated work.
2. Reproduce a small issue with synthetic fixtures and implement a focused change.
3. Follow shared Onesa design version `1.0.0`; inspect
   [the consumer manifest](design-system.consumer.json) and the protected
   [design-system guide](https://engineering.docs.onesa.eu/architecture/onesa-design-system).
   Test both OS preferences and a live transition without losing form/task state.
4. Run affected checks, contract validation and repository hygiene. Review the diff,
   update durable docs and record honest gaps. Preserve real release history.
5. Submit the reviewed dev candidate through staging. Production needs the current
   authorization and qualifying evidence; it is not part of first local setup.

Use `info@onesa.eu` or enabled private vulnerability reporting for safe private reports.
Do not attach credentials, real telemetry, personal data or unrestricted raw logs.
