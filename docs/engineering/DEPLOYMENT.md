# Simulator deployment and recovery

## Exclusive journal ownership during staging rollout

Render starts the replacement before stopping the old process. The existing staging
service must use `/api/v1/health` for rollout liveness. A replacement can wait up to
90 seconds for the existing journal owner; every other route, including login and
`/api/v1/ready`, returns 503 until it atomically acquires the lease and restores
history. It never steals an active lease or resumes a command. The prior instance's
graceful shutdown releases only its own lease; application acceptance waits for real
readiness before authenticated tests. A failed or timed-out startup remains
unavailable. No environment variable, paid disk or additional deployment is needed.

Apply the existing `repair-staging` operation only after exact dev/staging CI passes;
it selects process health only on the identified Free staging service. Production
layout, persistence and physical-control gates remain unchanged. Hosted rollout must
still verify replacement startup, preserved task history and operator authentication;
local two-instance tests alone do not qualify the service.

## Existing free native staging — 2026-10-12

The authenticated inspector confirmed that the existing Free/Frankfurt staging service uses native Python and the approved Turso journal. The registered `release-candidate.yml` owner workflow can inspect it from dev/staging, repair only its source/layout from staging after exact-source CI, and qualify the simulator with `target=staging`. Native staging uses the hash-locked requirements command, the repository Python version, and `sh start.sh` for one process. Production retains its separate Docker/durable-storage and owner/hardware gates.

Repair verifies the exact service/repository/region/plan, staging namespace and physical=false before writing branch/root/health/runtime commands and disabling automatic deployment. It preserves every private value and database record. The existing operator credentials must be preserved. A mismatched staging test password remains an authentication blocker until an approved existing test credential is supplied privately to CI. Direct Staging inspection reports only whether the named automation bypass resolves; secret-name metadata does not prove a usable value. Provider-bound staging edge identity stays in a private candidate-bound runner file and is removed after verification.

> Current private-Free release policy: [safeguards and external owner authorization](../development/PRIVATE_FREE_SAFEGUARDS.md). Legacy JSON approval is retired; native protection requirements below apply only to a verified supported configuration.

Cloud staging/release workflows, provider settings, secret locations, approval gates,
telemetry-only edge transport, monitoring and rollback are now documented in
[AUTOMATED_QUALIFICATION.md](AUTOMATED_QUALIFICATION.md). Render Free staging is
explicitly disposable simulation; durable cloud production remains blocked. The
private persistent-host procedure below remains a separately controlled alternative.

For remote durable task history on the existing Free Render staging service, see
[Turso staging](TURSO_STAGING.md). This staging-only journal avoids reliance on
Render's local filesystem. It does not satisfy or bypass production release gates.

For exact owner steps on an existing private persistent Docker host, see
[staging host setup](STAGING_HOST_SETUP.md). This does not create cloud resources
or promote the existing public interface.

Frontend/backend are independent release units. Existing public `robot.onesa.eu`
serves a static preview; the new simulator has not been promoted to that domain.
No new paid resource, production DNS change or physical control is authorized.

For durable storage, deploy the backend to an approved private simulator/edge host
with Python 3.11 or its Docker image, one process and a private persistent volume mounted at
`/app/storage`. Render Free does not supply this persistent SQLite volume; it must
not be represented as durable storage for this gateway. An independently qualified
free edge host or architecture-specific persistence decision is still required.
Do not attach the Portal or AI database to this simulator to bypass the missing host.

For HTTPS set the exact `ROBOT_PUBLIC_ORIGIN` and privately generated
`ROBOT_OPERATOR_PASSWORD_HASH`, operator name, database path, session/heartbeat
bounds and `ROBOT_ACTUATION_ENABLED=false`. Expose only the approved TLS gateway;
do not trust proxy headers or publish a ROS/DDS graph. The frontend needs only its
server-only credential-free `ROBOT_API_URL`. Keep API secrets out of frontend bundles.

Qualification: exact-SHA CI/security passes, protected target, liveness/core readiness,
authenticated login/proposal/approval/cancellation/stop/watchdog, restart persistence,
isolated backup restore, operator/alert ownership and independent security review.
Vercel Git deployment is disabled. Owner-dispatched cloud workflows are installed
locally but have not been activated or run.
Rollback must stop tasks, preserve its private database and retain the stop state;
never restore active sessions or resume a command from a prior process.

Backup SQLite using its online backup API into a restricted encrypted destination;
do not copy an open main file without WAL consistency. Test restoration only in an
isolated simulator: history persists, sessions revoke, stop stays latched, no task
resumes. Production restoration/retention and alert delivery need owner acceptance.
ROS 2 Jazzy interface definitions are preparatory, not a connected control adapter.

Public CI uses GitHub-hosted Ubuntu exclusively. The private-only reusable validation
gate includes the full simulator, cross-browser and container checks; it does not
register a runner or authorize a persistent host or physical control. See
[runner operations](SELF_HOSTED_RUNNER.md).

## Automatic software evidence

See [software/simulation qualification](AUTOMATED_QUALIFICATION.md). The artifact
does not authorize publishing a candidate or physical robot operation.

### Rolling staging origin changes

After resolving the exact-source protected Preview, the workflow authenticates and stops the existing synthetic simulation using the currently deployed origin, drains its history and fences the observed journal lease. Only then does it save the new Preview origin and deploy the backend. Render saved settings are not evidence of the running deployment configuration. If a prior attempt saved the new origin before handoff, reconcile only the staging `ROBOT_PUBLIC_ORIGIN` to a verified origin accepted by the live runtime before retrying. An empty login body returns HTTP422 for the accepted origin and HTTP403 for a rejected origin without attempting credentials. Preserve the existing operator, password and application origin protection.
