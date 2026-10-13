# Turso task history on Robot staging

Use the owner's existing database:
`libsql://onesa-ai-robot-backend-staging-druhustle.aws-eu-west-1.turso.io`.
No new resource, paid plan or DNS change is required by this code change. Check the
existing account's actual free-plan quota and overage policy before activation.

This staging-only mode persists task proposals, approval/completion/cancellation
history and final synthetic position in Turso. It uses Turso's authenticated
[SQL-over-HTTP protocol](https://docs.turso.tech/sdk/http/reference) with the existing
hash-locked HTTP client, rather than an Alpine-incompatible native extension.
There is no offline-write queue or embedded replica. Operator sessions, live joint
state, watchdog, stop authority, telemetry and authentication throttles are private
process-local data. The SQLite working store is in memory; it is not a backup.

## Set server configuration

On Render, open existing `onesa-ai-robot-backend_staging`
(`srv-db5k9ft9fdbs73d622cg`) → Environment. Save these settings **without deploying**
until the reviewed revision has passed the existing code/image/release checks:

```dotenv
ROBOT_DEPLOYMENT_ENVIRONMENT=staging
ROBOT_STORAGE_MODE=turso
ROBOT_TURSO_DATABASE_URL=libsql://onesa-ai-robot-backend-staging-druhustle.aws-eu-west-1.turso.io
ROBOT_TURSO_AUTH_TOKEN=REPLACE_DIRECTLY_IN_RENDER_WITH_DATABASE_SCOPED_TOKEN
ROBOT_PUBLIC_ORIGIN=https://REPLACE_WITH_ACTUAL_STAGING_FRONTEND_HOST
ROBOT_OPERATOR_NAME=operator
# Preserve the existing operator hash; do not regenerate it for staging automation.
ROBOT_OPERATOR_PASSWORD_HASH=KEEP_EXISTING_PRIVATE_RENDER_VALUE
ROBOT_ACTUATION_ENABLED=false
ROBOT_SESSION_SECONDS=900
ROBOT_HEARTBEAT_SECONDS=3
```

Keep `ROBOT_DATABASE_PATH=/app/storage/robot.sqlite3` if present for existing provider
preflight compatibility; this path is not used in Turso mode. Do not put the libSQL
URL into that file-path setting. Render supplies PORT. The existing staging service
uses native Python with root `onesa-ai-robot-backend`, start command `sh start.sh`,
health path `/api/v1/ready`, one worker and native Auto Deploy off. Preserve the
reviewed build/start settings. Docker artifacts remain independently checked in CI.

Reuse the existing database token when valid. On 2026-10-12, authenticated resource
inspection and a read-only SELECT1 verified this hyphenated staging endpoint with
the existing token. The prior unhyphenated `backendstaging` hostname was a
configuration error; fixing the URL does not require a token or operator reset.

For an independently authorized initial setup, select **this database** in Turso,
create a read/write database-scoped token with an appropriate expiry, and save it
directly in Render. Account-management tokens are not database authentication
tokens. The private CLI alternative for that initial setup is:

```sh
turso db tokens create onesa-ai-robot-backend-staging
```

This command prints a credential: run it privately; never paste its output into
chat, Git, a report or a CI artifact. A read-only token is insufficient for schema
initialization and task history. Track expiry/rotation with the operational owner.

Preserve the existing operator identity, roles and password/hash. Creation or
rotation requires explicit owner authorization and is independent of the Turso token.
Set Vercel's server-only `ROBOT_API_URL` in Preview to
`https://onesa-ai-robot-backend-staging.onrender.com`; use the real frontend origin
on Render. Keep Preview protection and the same-origin proxy, Origin/CSRF/session
checks and Vercel Git auto-deployment guard. No NEXT_PUBLIC database setting exists.

For the controlled staging workflow, configure these **nonsecret repository variables**:

```dotenv
STAGING_ROBOT_STORAGE_MODE=turso
STAGING_ROBOT_TURSO_DATABASE_URL=libsql://onesa-ai-robot-backend-staging-druhustle.aws-eu-west-1.turso.io
```

Existing separate staging provider IDs/operator/browser credentials still apply.
Do not add the Turso token to repository Actions: only the Render backend needs it.
The registered `release-candidate.yml` entrypoint accepts owner-triggered staging
dispatches on the staging branch. Its exact-source CI/evidence checks and mutually
exclusive environment/repository secret routing remain enforced. Production has
separate authorization gates; do not enable native auto-deploy or bypass them.

## Storage and failure behavior

Startup creates only `robot_simulation_tasks_v1` and `robot_simulation_lease_v1` in
this selected database. No existing SQLite file or unrelated table is imported,
overwritten or deleted. The journal uses one leased simulator process per database;
other writers are rejected. Staging and production must never share this database.
A lease is renewed every ten seconds and expires after thirty seconds according to
database time. Clean shutdown releases its own lease; after an abrupt crash the
replacement may need to wait for expiry. Expired owners cannot update task history.

Restart loads at most 10,000 history entries, cancels unfinished work, revokes
sessions and starts stopped. Accepted task mutations require cloud acknowledgement.
Approval grants local simulation execution authority only after acknowledgement
and a fresh session/safety check. A single task upsert is atomic. Multi-task stop
history is not one cloud transaction: if any acknowledgement fails, return 503,
keep simulation locally stopped and reconcile unfinished rows on recovery restart.
An ambiguous timeout never triggers a transparent retry or fake success.

Readiness uses the background lease proof (at most fifteen seconds old), not a
new remote query per anonymous request. A failed renewal immediately fails readiness;
an expired cached proof also latches stop. This avoids public readiness traffic
exhausting the database pool. It is bounded recent connectivity evidence, not a
promise that the provider cannot fail between checks.

The watchdog ticks locally at 20 Hz without network calls. Only task lifecycle
changes are journaled. Request/read deadlines, response limits and a bounded HTTP
pool prevent provider delays from blocking that loop. Storage failure latches stop,
clears the active task and makes readiness unavailable. Liveness stays separate;
stop remains effective locally even when durable acknowledgement returns 503.
Recover provider access and restart explicitly; reset alone cannot hide a failed
journal. Physical actuation remains unconditionally disabled.

## Acceptance before claiming hosted persistence

1. Deploy the reviewed staging revision through the authorized workflow. Verify
   its exact SHA, startup logs and `/api/v1/ready` reporting `storage_mode=turso`.
2. Sign in, reset, propose/approve a synthetic task, heartbeat, cancel and inspect
   history. In Turso confirm the corresponding task row and final state.
3. Restart the same isolated staging service. History must remain; the old session
   must fail, stop must be latched and no unfinished task may resume.
4. On an isolated test target, exercise token expiry/unavailable storage: readiness
   and unacknowledged mutations return 503 while the local simulator stays stopped.
5. Export/restore only synthetic task data into a separate isolated database and
   repeat restart/no-replay checks. Record retention, access and quota monitoring.

Local regressions use actual simulator handlers, SQLite SQL and a synthetic Turso
HTTP boundary. They do not prove this live database's credentials, quotas, backup
policy or hosted reachability. No actual cloud schema mutation has been performed.
Production Turso startup remains rejected until a separate recovery/security/release
qualification approves that architecture. This is software simulation, not hardware.

Local implementation evidence on 2026-10-11: Python 3.11 simulator tests and release
failure-path tests, Ruff, mypy, generated API/client drift, actionlint, publication
hygiene and the hash-locked nonroot Alpine runtime build were checked. Provider
credentials, actual hosted connectivity and isolated Turso export/restore remain
pending. Public or physical production is not authorized by these local results.

## Rolling deployment handoff

Actual staging deploy logs on 12 October 2026 report `Simulation journal already has
a live owner`. The exclusive lease is required; Render keeps the old instance running
until the new one is healthy, so a second journal owner cannot start during that overlap.
The owner-only staging release now authenticates the existing operator, stops simulation,
flushes pending task history, signs out and expires only the observed staging lease using
an owner comparison. The old instance can no longer renew or write; the new exact-source
instance acquires authority normally. No task/history rows are deleted, no operator or
credential is replaced, and no physical actuation is enabled. The handoff is limited to
the pinned free staging Render service and the verified hyphenated Turso hostname.

All source/security gates precede this operation. Hosted readiness, authentication,
replay denial and browser tests remain mandatory afterwards. A failed handoff prevents
deployment. If the deployment subsequently fails, restore the last qualified exact
commit through the existing owner-controlled staging recovery path; the expired old
lease is not renewed automatically. This may cause staging downtime and does not claim
zero-downtime service. Production uses its separate approved deployment controls.
See [Render deployment sequencing](https://render.com/docs/deploys#zero-downtime-deploys).

The verified remote-journal staging profile does not use `ROBOT_DATABASE_PATH`; its erroneous libsql duplicate was removed from Render on 13 October 2026. Keep this supported setting for local/persistent filesystem modes. No existing password, Turso credential or history was changed.
