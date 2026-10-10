# Simulator deployment and recovery

Frontend/backend are independent release units. Existing public `robot.onesa.eu`
serves a static preview; the new simulator has not been promoted to that domain.
No new paid resource, production DNS change or physical control is authorized.

Deploy the backend only to an approved private simulator/edge host with Python 3.11
or its Docker image, one process and a private persistent volume mounted at
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
Vercel Git deployment is disabled. No automatic workflow publishes this candidate.
Rollback must stop tasks, preserve its private database and retain the stop state;
never restore active sessions or resume a command from a prior process.

Backup SQLite using its online backup API into a restricted encrypted destination;
do not copy an open main file without WAL consistency. Test restoration only in an
isolated simulator: history persists, sessions revoke, stop stays latched, no task
resumes. Production restoration/retention and alert delivery need owner acceptance.
ROS 2 Jazzy interface definitions are preparatory, not a connected control adapter.
