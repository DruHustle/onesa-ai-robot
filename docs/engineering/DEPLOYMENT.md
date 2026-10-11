# Planned deployment and release gates

There is no deployment target, application image, runtime or hardware integration yet.
Do not deploy this scaffold. Frontend/backend are separate future release units within
this repository; version their API and authenticate AI-platform access with a scoped
server-only token. Never place control credentials in browser configuration.

Before implementation release: choose approved runtimes/hardware/network boundaries,
define authentication/authorization and audit logs, qualify simulation and safety
controls, emergency stop and command limits, review data handling, and provide
per-application Dockerfiles and health checks. Offline/simulation CI precedes any
explicitly authorized hardware testing. Keep model weights/telemetry/uploads outside Git.

Candidate packaging must be manually invoked per application, reference passing
exact-revision CI, and require protected environment approval for promotion. Production
secrets should use a secret manager; rollback must preserve state and disable actuation.
The scaffold CI is not a robot validation or deployment pipeline. `release-candidate.yml` is a manual packaging template that fails closed without the
selected application Dockerfile. It does not deploy or publish. Add application test
gates and qualify targets before activation.


## Intended hostname — 2026-10-10

The owner selected `robot.onesa.eu` for the future operator interface. This is a
planned address, not a live deployment. Reserve it in the domain plan; attach DNS
only once an implemented and qualified frontend has a confirmed hosting target.
The gateway remains independently deployable and authenticated; selecting the
hostname does not implement or authorize hardware control.

## Local CI infrastructure

Runner provisioning and workflow routing are independent of application release: see [SELF_HOSTED_RUNNER.md](SELF_HOSTED_RUNNER.md). Main remains scaffold-only; simulator/ROS 2/hardware qualification must never be inferred from its boundary checks. Audit branches must retain their implemented application tests when incorporating the runner migration.

## Automatic Git deployment guard

Root and frontend `vercel.json` set `git.deploymentEnabled: false`, preventing
Vercel's Git integration from promoting this scaffold during a CI-only merge.
This does not invoke a CLI release or qualify production; audit implementation
must retain its frontend guard and established exact-revision release checks.
See [Vercel Git configuration](https://vercel.com/docs/project-configuration/git-configuration).
