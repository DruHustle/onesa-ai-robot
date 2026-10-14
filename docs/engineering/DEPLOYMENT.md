# Robot simulator deployment and recovery

Audience/classification: authorized engineering / INTERNAL. Owner: Robot engineering.
Reviewed: 2026-10-14. Scope: software simulation only. Existing immutable deployment
receipts remain in the restricted release store; local changes are not hosted acceptance.

## Current deployed baseline and storage

The October 14 production source is `16381086192dc34c8ad7ea40c43ef6d178b00904`
at `https://robot.onesa.eu`: Render `dep-db7f3oe7bikc73aldipg` and Vercel
`dpl_J13jsKeKNGCMqMWbdUV9i45JUcGm`. Exact main CI, fresh hosted staging,
qualification `38501657824` and owner authorization `38501859388` passed before
deployment. Actual production API/safety/edge checks are 13/13 PASS. Initial hosted
browser acceptance is **FAIL: 67/69 passed**, with two Chromium sign-ins returning
503 Gateway unavailable; Firefox and WebKit each passed all 23. The provider receipt
remains BLOCKED at the mandatory browser gate. Subsequent bounded readiness samples
passed, but Render cold wake as the specific cause is not verified. Existing credentials
and all three earlier history records were retained; the confirmed idle stop latch
was restored and physical actuation remains disabled. Restricted evidence is in
`docs/internal/release-audit/evidence/system-design-v2-main-1638108/`; the failed suite
is retained and a qualified frontend recovery release must pass actual acceptance.

The earlier October 13 recovery baseline is source
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

Console sign-in checks credential-free readiness with a 20-second upper bound before
submitting credentials once. Temporary unavailability retains masked input for an
explicit retry; successful or rejected authentication clears passwords. These checks
exist only in the operator shell. Readiness cannot grant authority, and approvals,
reset, task creation or control commands are never automatically replayed.

## Independent frontend delivery

Full releases remain the default. An owner may explicitly select `release_mode:
frontend-only` in the existing staging workflow or candidate bridge, with the prior
`baseline_authorization_run`. The current baseline is owner authorization `38501859388`
for backend source 1638108. The application packaging choice alone does not enable reuse.

The verifier reads immutable GitHub authorization, qualification, CI/build and staging
artifacts directly. It rejects stale/superseded/revoked/foreign proofs, incorrect owner
or branch/event, altered artifacts and chains of retained-component proofs. It derives
backend tree, Render reference/runtime context, root configuration, generated API/schema,
hand-owned client contract, ROS and edge identities from exact GitHub commit objects.
All must be byte-identical and the baseline must be an ancestor. Every new candidate
still requires exact main CI, fresh hosted staging, new qualification and a new owner
authorization. No caller-supplied PASS record or substituted repository SHA is accepted.

Staging verifies existing baseline source/readiness before journal handoff, binds only
the verified new protected Preview origin and purposefully restarts the unchanged
baseline backend source. Its receipt records the actual baseline backend commit and
new candidate frontend commit. Production's canonical origin stays fixed: after a
fresh external gate, set `ROBOT_AUTHORIZATION_RUN` to the new authorization and run
`cloud.py retain-backend Production --directory <private-release-directory>` from the
clean reviewed main checkout before the Vercel operation. This command performs no
provider write; it rederives authorization, verifies actual latest live backend source,
runtime bindings and readiness, and saves the retained deployment identity.

Preserve the private preflight record from the new trusted qualification. Final receipts
independently refresh component provenance and actual provider source/readiness, compare
the release's complete runtime configuration privately, and record both actual component
versions and prior backend build/authorization provenance. Credential digests remain in
ephemeral private files, never in Git, printed logs or uploaded receipt artifacts. The
retained backend must not be redeployed for icons/CSS. Missing/expired baseline proof or
backend/contract drift blocks this mode; never pass a false SHA to smoke or receipt checks.

Route `/api/v1/:__onesa_route*` to `api/gateway.mjs`. The adapter removes only one
metadata value matching the original nested API path; reject extra, duplicate or
mismatched values, arbitrary upstreams and direct gateway/private paths. Preserve
session-cookie filtering, exact Origin/CSRF, TLS and no-store. Provider bypass secrets
must never be forwarded to Render. Check real Vercel nested artifacts and hosted routes.

## Safe staging origin handoff and rolling journal ownership

1. Resolve the exact-source protected Preview and inspect the existing running origin.
2. Authenticate the existing synthetic test operator using its approved private test
   credential. Before stopping, verify simulation mode, disabled physical actuation,
   an already latched stop, no active task, no running/proposed recent history and zero
   pending rows across the complete existing staging journal. The handoff sends no
   stop or cancellation request. Preserve unknown work and coordinate its owner if
   any check fails. Recheck the latched idle runtime and unchanged history, then fence
   only the observed lease using an atomic owner and no-pending-work predicate. Verify
   that same owner, expired lease and idle journal together. A newly acknowledged
   pending task prevents fencing; existing backend writes require the live lease.
   The qualification fixture is owner-coordinated and synthetic; snapshots do not
   certify arbitrary concurrent operator activity. Only the run-owned acceptance
   scenario may restore its stop latch after its own completed task and idle readback.
   Preserve credentials and production; never cancel preexisting work to pass a release.
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
