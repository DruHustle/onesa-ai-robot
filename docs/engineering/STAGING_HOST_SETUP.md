# Private Robot staging host setup

## Owner-created Render targets

The owner supplied `onesa-ai-robot-backend` (`srv-db5k88flk1mc73aa9110`,
`https://onesa-ai-robot-backend.onrender.com`) and `onesa-ai-robot-backend_staging`
(`srv-db5k9ft9fdbs73d622cg`,
`https://onesa-ai-robot-backend-staging.onrender.com`). Do not create duplicate
resources. Plan, region, repository/branch, protected ingress and persistent storage
are not verified. Public readiness requests timed out; this does not prove whether
the cause is startup, cold start or configuration. No provider writes or deployment
were made, and these IDs do not qualify a production or physical release.

For staging, the intended repository is `DruHustle/onesa-ai-robot`, reviewed branch
`audit/robot-simulation-acceptance`, Docker root `onesa-ai-robot-backend`, Dockerfile
`./Dockerfile`, context `.`, blank Docker Command override and Auto Deploy off.
Confirm these before manually saving changes that might trigger deployment.
The backend image listens on Render's `PORT`; health/readiness is `/api/v1/ready`.
Do not select a paid instance/disk under the free-only policy. Render Free cannot
provide the required durable SQLite volume. Keep hosted simulator acceptance blocked
until an approved persistent target or separately reviewed persistence change exists.
The source frontend is an independent Node server/proxy; a backend service alone
does not deploy that interface or qualify the old public static preview.

## Existing private persistent host

Use an existing owner-approved machine with Docker and persistent disk for the
software simulator. This adds no cloud compute subscription. Do not use Render
Free for this SQLite gateway: its files are lost on restart/redeploy and it cannot
attach a persistent disk. See [Render Free limits](https://render.com/docs/free).
The existing public Vercel robot preview is separate from this authenticated
simulator; do not claim it already hosts these workflows.

These commands are for a private local staging host. Remote operation requires
an approved authenticated TLS gateway and its real hostname; loopback instructions
do not publish a production service. No ROS network or physical actuators are used.

Clone using your existing private GitHub access, then select the reviewed candidate:

```sh
gh repo clone DruHustle/onesa-ai-robot
cd onesa-ai-robot
git switch --track origin/audit/robot-simulation-acceptance
docker build -t onesa-robot-staging-api ./onesa-ai-robot-backend
docker build -t onesa-robot-staging-ui ./onesa-ai-robot-frontend
docker run --rm -it onesa-robot-staging-api python -m robot_api.security
```

The last command prompts privately for a new operator password and produces its
scrypt hash. Store the hash in a restricted host-only env file outside the checkout,
for example `$HOME/.config/onesa/robot-staging.env`, with directory mode700/file600:

```dotenv
ROBOT_PUBLIC_ORIGIN=http://localhost:3431
ROBOT_OPERATOR_NAME=operator
ROBOT_OPERATOR_PASSWORD_HASH=REPLACE_WITH_PRIVATELY_GENERATED_SCRYPT_HASH
ROBOT_DATABASE_PATH=/app/storage/robot.sqlite3
ROBOT_ACTUATION_ENABLED=false
ROBOT_SESSION_SECONDS=900
ROBOT_HEARTBEAT_SECONDS=3
PORT=8431
```

Run one backend process and a separate frontend on a dedicated private network:

```sh
docker network create onesa-robot-staging
docker volume create onesa-robot-staging-storage
docker run -d --name onesa-robot-staging-api --network onesa-robot-staging \
  --network-alias backend --restart unless-stopped \
  --env-file "$HOME/.config/onesa/robot-staging.env" \
  --mount source=onesa-robot-staging-storage,target=/app/storage \
  onesa-robot-staging-api
docker run -d --name onesa-robot-staging-ui --network onesa-robot-staging \
  --restart unless-stopped -p 127.0.0.1:3431:3431 \
  -e ROBOT_API_URL=http://backend:8431 onesa-robot-staging-ui
curl -i http://localhost:3431/api/v1/ready
```

The explicit `backend` network alias matches the frontend's private HTTP allowlist.
The backend is not published to a host port; the interface is bound to loopback.
The named volume preserves state between container replacements; never delete that
volume as a routine redeploy. Containers remain non-root, without privileged mode
or hardware access. Log in at `http://localhost:3431` and verify simulation labels,
proposal/approval, cancellation, stop/reset, watchdog and logout. Restart the API
and confirm history persists, sessions revoke and no task resumes. Do not interpret
readiness alone as complete operator or recovery acceptance.

Back up SQLite using the documented online backup procedure and restore only into
an isolated test instance; do not copy an active database file without WAL consistency.
Share only the approved host identifier and intended access method for coordinated
deployment, never the password/hash/env file. Keep physical actuation disabled.

If no existing host is available, a provider's Always Free persistent VM can be
evaluated separately, but account/terms, actual free capacity, architecture and
quotas must be verified before provisioning. Trial credit is not an ongoing free
host. No paid resource or provider registration is authorized by this guide.
