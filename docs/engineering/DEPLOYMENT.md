# Simulator deployment and recovery

Cloud staging/release workflows, provider settings, secret locations, approval gates,
telemetry-only edge transport, monitoring and rollback are now documented in
[AUTOMATED_QUALIFICATION.md](AUTOMATED_QUALIFICATION.md). Render Free staging is
explicitly disposable simulation; durable cloud production remains blocked. The
private persistent-host procedure below remains a separately controlled alternative.

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
