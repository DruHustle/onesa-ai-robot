# Robot simulator deployment and recovery

Audience/classification: authorized engineering / INTERNAL. Owner: Robot engineering.
Reviewed: 2026-10-14. Scope: software simulation only. Existing immutable deployment
receipts remain in the restricted release store; local changes are not hosted acceptance.

## Current deployed baseline and storage

The October 13 production baseline is source
`b0d40c6d2ccab2b1663166ebf311b4a9755ad045` at `https://robot.onesa.eu`. Restricted
`data/runtime/production-release/hosted-acceptance.json` records all 13 hosted checks
PASS at 20:03:33 UTC. Render deployment `dep-db78k3a5b2lc73euuvl0`, Vercel deployment
`dpl_2xe3R4Nphug6xBZ317onVEiPwJP7`; owner authorization run `38410878463` binds the
qualification run `38410516546`. These receipts attest that baseline, not a later diff.
Physical actuation is disabled. Scheduled journal recovery, alerts and physical safety
remain separate gates; the baseline does not manufacture their approval.

The owner-selected production service `srv-db5k88flk1mc73aa9110` uses the existing
`libsql://onesa-ai-robot-backend-druhustle.aws-eu-west-1.turso.io` task journal on Free
Frankfurt native Render. `ROBOT_STORAGE_MODE=turso` and
`ROBOT_DEPLOYMENT_ENVIRONMENT=production` permit only that production database.
Staging uses its separate verified hyphenated `onesa-ai-robot-backend-staging`
database. Production and staging database-scoped tokens and operator-password hashes
must remain distinct. Never reset operator credentials to make a test pass.

Ephemeral SQLite remains blocked for production. Turso uses an in-memory SQLite
working store and exclusive remote journal, with process-local revoked-on-restart
sessions. Do not set an unused cloud filesystem database path, attach either sibling's
database, claim a paid disk or silently fall back to ephemeral history.

## Configuration and authority

Inspect current providers and private bindings before a write. Native builds use
`python -m pip install --require-hashes -r requirements.lock` and single-process
`sh start.sh` with the repository Python version. Render automatic deployment remains
off. Use `/api/v1/health` for rollout liveness and `/api/v1/ready` for acceptance.
Preserve the actual existing operator, session/heartbeat limits, independent synthetic
edge identity and `ROBOT_ACTUATION_ENABLED=false`. Set the exact browser origin; server-only
Vercel `ROBOT_API_URL` targets the corresponding Render origin.

Credentials stay in the approved private provider configuration and external release
custody. Inspect only presence/scope and boolean usability; do not print environment
values, hashes, tokens or provider bodies. Rotate an expiring database token through
the approved secure process without disturbing operator passwords or journal data.

Keep only **dev**, **staging** and **main** permanently. Normal integration is
**dev → staging → main**; temporary security PR/candidate exceptions follow
[the scoped security procedure](CI_CD.md#security-pr-integration-and-urgent-candidates).
Exact-source CI, hosted staging, artifact/qualification,
applicable operations/content scope and actual current owner authority precede release.
Do not claim private GitHub Free supports native protection without real readback.
Provider Git staging previews are the staging frontend authority; production Vercel
and Render use the established controlled external handoff. See
[AUTOMATED_QUALIFICATION.md](AUTOMATED_QUALIFICATION.md) and current restricted receipts.

## Gateway and product routes

The public `/` product page has no private API scripts. `/console` serves the operator
sign-in shell; its JavaScript contains no private state or credentials, and all
telemetry/history/control reads require a valid backend operator session. Static shell
availability does not grant access. Appearance follows OS preference independently.
Protected status responses supply observation time and trusted deployment environment.

Route `/api/v1/:__onesa_route*` to `api/gateway.mjs`. The adapter removes only one
metadata value matching the original nested API path; reject extra, duplicate or
mismatched values, arbitrary upstreams and direct gateway/private paths. Preserve
session-cookie filtering, exact Origin/CSRF, TLS and no-store. Provider bypass secrets
must never be forwarded to Render. Check real Vercel nested artifacts and hosted routes.

## Safe staging origin handoff and rolling journal ownership

1. Resolve the exact-source protected Preview and inspect the existing running origin.
2. Authenticate the existing synthetic test operator using its approved private test
   credential. Stop the simulator, drain task history and fence only the observed
   staging journal lease. Preserve records, credentials and production.
3. Save the new verified Preview origin, then deploy the exact qualified source. Saved
   Render environment changes do not attest the running configuration. If an earlier
   attempt changed saved origin prematurely, reconcile only staging to a verified
   origin accepted by the live runtime; never weaken the origin check.
4. The replacement may report liveness while waiting up to 90 seconds for the old
   instance to release its lease. Login/readiness/all application routes return 503
   until exclusive ownership and history are restored. It never steals an active lease.
5. Verify actual readiness, preserved history, operator authentication and complete
   simulation/edge/browser acceptance. A login PASS cannot qualify independent device
   telemetry. Failing startup stays unavailable; no automatic resume occurs.

Render Free wake-up can produce a bounded initial 503 through the gateway. Record cold
and warm observations separately; do not hide an unresolved persistent outage behind
retry or keep a free instance artificially awake.

## Recovery, rollback and administrative tunnel

Stop tasks before rollback, preserve the private journal and retain the stop latch.
Sessions revoke and unfinished tasks cancel on restart. Recheck origin/API/schema/
artifact compatibility. Do not restore active sessions or automatically replay commands.
Test backup/restoration only in an isolated authorized destination; prove retained
history, fenced single-writer ownership, revoked authority and no resumed task. Scheduled
backup execution, key recovery, retention and alert delivery need their own actual evidence.

The owner reports a **Tailscale tunnel between the PC and VM** for private administration.
Its console is `https://console.tailscale.com/`. Treat it as a distinct encrypted
administrative boundary, with existing identity/device approval and scoped tailnet
policy; verify actual node identity, ACL/grants, expiry and active transport through
read-only inspection before claiming runtime PASS. Do not disclose node keys or enlarge
SSH/firewall access. The tunnel is not cloud-to-edge Robot motion transport, does not
replace operator/device authorization and must not expose DDS, actuators or model listeners.

No physical driver, camera/STT/VLM/TTS/VLA integration or installed edge-control update
is authorized by a software release. Keep separate software, ROS compatibility, edge
installation, real-model and physical-hardware verdicts.
