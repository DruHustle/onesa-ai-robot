# Robot simulation API

Python 3.11 / FastAPI. Install independently:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m ruff check robot_api tests
.venv/bin/python -m pytest -q
.venv/bin/python -m robot_api.security
```

Generate the operator password hash privately and store it as
`ROBOT_OPERATOR_PASSWORD_HASH`; do not paste the password/hash in chat or Git.
Populate the server settings in `.env.example` in an ignored local environment file
or approved secret manager. This app deliberately does not auto-load arbitrary .env
files. Export the settings securely in the process environment before `sh start.sh`.
For a development env file, use `.venv/bin/python -m uvicorn
robot_api.main:create_app --factory --env-file .env.local --host 127.0.0.1 --port 8431
--workers 1 --no-proxy-headers --no-access-log` as one command.

The production command is `sh /app/start.sh`; PORT defaults to 8431. One process
owns a persistent SQLite database at `ROBOT_DATABASE_PATH` (default
`storage/robot.sqlite3`), and the enclosing directory/volume must be private. Runtime
is non-root. `/api/v1/health` is process liveness, `/api/v1/ready` verifies database
and watchdog state for simulation, and authenticated `/api/v1/status` labels every
unconfigured capability honestly. Neither endpoint approves physical operation.

Cookie sessions are opaque, hashed in storage, scoped to `/api/v1`, HttpOnly,
SameSite Strict and Secure on HTTPS. Mutations need exact Origin plus session CSRF
proof. Stop is operator-authorized. Reset and approval also require password proof.
There is one configured operator identity; multi-user roles are not claimed. Login
attempts and active sessions are bounded. Tasks/history are bounded and persisted.
Mutating request bodies are limited to 16 KiB and a five-second total receive
deadline, including clients that trickle bytes. Incomplete requests return 408;
this does not replace frontend/network rate limits or authorize hardware control.

`docker build -t onesa-robot-api:local .` builds independently. Keep the API private
behind the approved same-origin frontend/TLS boundary. No credential is a frontend
public setting. Physical actuation=true always fails startup. No migration or test
uses either sibling product's database.
