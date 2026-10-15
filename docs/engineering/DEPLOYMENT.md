# Robot simulator deployment and recovery

Audience/classification: authorized engineering / INTERNAL. Owner: Robot engineering.
Reviewed: 2026-10-14. Scope: software simulation only. Existing immutable deployment
receipts remain in the restricted release store; local changes are not hosted acceptance.

## Journal connection failures

The journal permits one HTTPX connection-establishment retry before a request is
sent. HTTP phase deadlines remain one second and the outer operation deadline stays
two seconds. Pool bounds, lease fencing, heartbeat and stop behavior are unchanged.
Read/write/protocol failures never resend a statement. A lost acknowledgement still
requires one exact seven-field read under the same live lease; uncertainty fails closed.
Diagnostics now record only an allowlisted HTTP exception class and reconciliation
outcome alongside the existing fixed categories, never exception text or row contents.
The earlier transport failure's exact subtype was not captured; do not retroactively
claim it was a connect error. See [HTTPX transport retry semantics](https://www.python-httpx.org/advanced/transports/).

## Restricted development release and owner deferral

Robot is under development. Its protected operator interface supports authorized
software development/testing, with essential authentication sessions, operator-linked
synthetic history and necessary security diagnostics. It is not a customer launch or
an integrated physical controller. The owner explicitly deferred the legal-basis,
history/backup/provider-log retention and existing-provider processing/transfer records
until launch on 2026-10-15. Those records remain unapproved; no legal compliance,
executed provider agreement or external lawyer certification is inferred.

Use the existing credential-free manual `free-authorization.yml` decision, selecting
`defer_development_privacy=true` only for that reviewed restricted development scope.
The immutable owner artifact records `DEFERRED_BY_OWNER_UNTIL_LAUNCH`, separately from
the untouched qualification's blocked legal/operations fields. The source must state
`Under development` and protected development/testing access. An external production
preflight may carry that exact deferral only after `free_gate` revalidates the latest
owner artifact, exact main, fresh CI/staging, source digest and current authorization.
GitHub Actions cannot use this exception to deploy. It grants no operations PASS:
current preservation, backup/recovery, operating limits and scoped operations review
are still required. Authentication, CSRF, private telemetry, credentials, history and
physical-controller safety requirements are unchanged.

Keep the deferred records in the existing restricted review and master evidence
register as launch blockers. A change to customer access, processing purpose,
providers or physical operation needs its own review; this decision cannot grant it.
Revoking/superseding the owner authorization or changing the exact candidate invalidates
the handoff. The default authorization path and all other production gates remain.

## Current deployed baseline and storage

The current October 14 production frontend is
`56ce52f20ddf7a491de0b33a3805d0c02cc0d345`, Vercel
`dpl_ENwtg1yhAww2dZURnrabR4b5NraD`, at `https://robot.onesa.eu`.
It retains backend `16381086192dc34c8ad7ea40c43ef6d178b00904`, Render
`dep-db7f3oe7bikc73aldipg`. The source-bound qualification and owner authorization
preceded this frontend-only delivery; actual API acceptance passed 13/13, while
mandatory browser acceptance **failed at 80/81**. Preserve the failed WebKit
sign-out observation; the precise original focus state was not captured. The later
explicit originating-form correction has passed source/local and earlier hosted
staging checks but has not been deployed to production. Journal recovery-required
503s were observed separately at 09:09 and 09:32 UTC; a bounded read-only readiness
observation passed at 09:59, followed by stable complete-history/idle checks at
10:05. These observations neither explain the latch nor qualify a new release.
No production restart was performed. Restricted records are in
`docs/internal/release-audit/evidence/system-design-v2-main-56ce52f/`.

The earlier October 14 production source was
`16381086192dc34c8ad7ea40c43ef6d178b00904`: the same Render deployment and Vercel
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

The owner-requested administration software is a new candidate, not part of the
previous 83f7579 qualification. After its own exact-source CI and staging checks,
bind `ROBOT_ADMINISTRATOR_NAME` only to the existing approved operator name in
each intended environment. Preserve the operator/password/device credentials,
journal and other configuration. Do not enable a different account or infer an
administrator role from browser markup or a request body. The protected console
then offers session-bound allow/block permission, with separate hardware state.
Hardware is still in development; no real controller or physical actuation is
claimed. A missing administrator designation fails the newly mandatory hosted
`administrator_operation_permission` check, rather than silently skipping it.
The 83f7579 15-check/84-view result remains valid only for its older source;
fresh qualification is required for the new control/authentication surface.

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

## Journal availability diagnosis and prepared full release

The exact-main staging run `38555383546` for
`53803249d27de78af4ed971dac10feb139370266` failed its mandatory hosted suite at
**59/84** (Chromium 28/28, Firefox 18/28, WebKit 13/28). Its source tree matches
the earlier `826e65e` staging run that passed 15 API/safety checks and all 84 browser
cases. That earlier PASS does not qualify this failed run. No trusted staging
receipt artifact was generated. Preserve the complete failed log and sanitized
diagnosis in the existing restricted `system-design-v2-form-origin-ca75187` audit.

At 11:43 UTC a bounded read-only direct staging check returned the fixed
recovery-required 503. Two complete SELECT-only snapshots of the current journal
matched: 348 rows, zero pending tasks and one expired lease. These compare only
that observed window; no complete before-suite comparator survived the failed run.
The sampled provider logs contained no exception type or operation phase. The
underlying trigger remains unproven. Source inspection disproved the hypothesis
that reset marks all historical tasks dirty: reset changes the safety flag, and
cancellation marks only running/proposed tasks. Flush-before-renewal is a source
timing observation, not evidence of this incident's cause.

The prepared diagnostic change emits one warning in the existing protected backend
log when journal failure first latches. It records only an allowlisted category,
an explicit operation phase, clamped integer monotonic elapsed milliseconds and an
optional numeric HTTP status. It excludes exception text, SQL, URLs, tokens, task
identifiers, row contents, raw responses and tracebacks. Anonymous 503 responses
remain unchanged. A timeout category identifies a timed-out boundary; ownership
means a guarded statement did not return the expected owner. Neither proves a
provider outage or permits automatic recovery. A stale-lease warning identifies
the existing readiness freshness check, not the cause of missed renewal.

The patch preserves the one-second HTTP budget, two-second overall RPC budget,
10-second renewal, 15-second readiness freshness and 30-second lease, together
with existing flush order, fencing, cancellation, watchdog and no-retry behavior.
Lifecycle cancellation propagates; an ambiguous write is never replayed. This
backend change requires a **full** release with new exact-source CI, fresh hosted
staging, immutable artifacts, qualification and owner authorization. Earlier
frontend-only retained-backend proofs and prepared builds do not attest it.

Before any provider operation, present the reviewed source, isolated negative
tests, actual failed-run evidence and narrowly scoped plan to the release owner.
Confirm the exact existing staging service, source/configuration, complete history,
already-stopped idle state, zero pending work and current lease/deployment/Actions
state. Preserve unknown work and hold if any check is inconclusive. A failed journal
does not authorize a stop, lease edit, token rotation, history deletion or production
restart. No recovery or additional hosted attempt is automatic. Record attempts
for the same unresolved episode and stop by the master limit of three; the failed
exact-main suite above is attempt one, with zero recovery restarts or retries.
After any separately authorized staging cutover, require actual history/readiness
and the complete 15/84 hosted gates before normal main qualification. Production
provider writes require a new concrete owner-reviewed plan and fresh external gate.

## Render deployment receipts and bounded observation

`scripts/deploy_render.py` separates a single create request from observation of
the accepted deployment. It saves an owner-only sanitized receipt before the
request, immediately after acceptance, on status transitions and on observation
failure. The adjacent `render-preflight.json` contains only the source/run binding;
it grants no deployment or acceptance authority. Both existing cloud workflows
upload these two exact files as `render-deployment-observation` immediately after
the backend step, including on failure, before application acceptance. They never
upload a directory containing credentials, runtime configuration or task data.

The initial observation window remains 1,800 seconds, including provider preflight
and submission. Each complete HTTP operation, including its response body, has a
20-second deadline. GET rate-limit recovery permits at most three requests with a
bounded delay; POST is never retried. Polling backs off from five to thirty seconds
and reports transitions or a summary every ninety seconds. The backend step has
a 32-minute limit and the immediate artifact step two minutes; the existing outer
job stays at sixty minutes. No provider build limit was increased: Render documents
up to 120 minutes for a build command. Longer work needs a controlled observation
continuation, not a runner waiting indefinitely or another build request.

An observation timeout exits nonzero, blocks subsequent deployment/acceptance and
records that Render may continue independently. `build_failed`, `update_failed`
and `pre_deploy_failed` are confirmed provider failures; `canceled` and
`deactivated` are distinct non-success outcomes. `live` succeeds only when the
exact source is still the latest live deployment. It still records application
acceptance as NOT TESTED and grants no promotion authority. Unknown states,
wrong sources, changed targets and malformed responses fail closed.

To observe an existing version-2 receipt, first retrieve the exact original
`render-deployment-observation` artifact from the independently verified owner run.
Keep the downloaded original and artifact digest in the restricted evidence store.
Copy its two files into a new owner-only continuation directory, set the receipt
to mode 0600, and independently pin the copied receipt's SHA256. Using the existing
authorized Render credential in private operator custody, run:

```sh
python3 scripts/deploy_render.py --environment Staging \
  --observe-id dep-EXACT_DEPLOYMENT_ID --candidate EXACT_REQUESTED_CANDIDATE_SHA \
  --preflight /private/continuation/render-preflight.json \
  --receipt /private/continuation/render.json --receipt-sha256 EXACT_RECEIPT_SHA256 \
  --wait-seconds 1800 --request-timeout 20
```

The existing `RENDER_SERVICE_ID` and `GITHUB_REF` must match that environment's
fixed service and permanent branch. The observer validates the receipt hash,
original source/run binding, service configuration and actual deployment commit;
its transport rejects every POST. It makes no application, operator, SQL,
cancellation, restart or cache-clear request. Resuming observation consumes no
full hosted qualification attempt and cannot resume skipped acceptance jobs.
After any actual live result, follow the existing source-bound staging, approval
and hosted acceptance process within its separately authorized attempt budget.

For an ambiguous create response, preserve the request intent and reconcile the
provider's exact recent deployments before any further submission. An existing
active deployment or matching source blocks a duplicate full create. Do not erase
the receipt to evade that guard. The older script saved a receipt only on success;
a failed legacy run may have no receipt. Never fabricate its original preflight
or claim it can be resumed through the version-2 path. Reconcile its immutable
workflow log and exact provider record separately in the existing restricted audit.

The October 14 run `38628644160` targeted the fixed **staging** service and commit
`0299570`, not production. Its local 1,800-second timeout did not cancel Render.
The subsequent operator-owned cancellation was separately verified; no hosted
API/browser acceptance started. Current restricted evidence preserves provider
times, serving source, the zero-entry build-log readback and Render's reported
regional build incident. No dependency, model, hardware package, memory, cache or
quota cause is inferred without actual build evidence. No build file or hosting
plan change is justified by that empty log result.

Sources: [Render deploy states](https://api-docs.render.com/reference/retrieve-deploy),
[rate limits](https://api-docs.render.com/reference/rate-limiting),
[build pipeline limits](https://render.com/docs/build-pipeline).

## Recovery, rollback and administrative tunnel

For a task-save timeout or transport loss, the journal may have committed before
the acknowledgement arrived. The client performs one bounded read of all seven
persisted fields, requiring its unchanged, unexpired writer lease. An exact match
acknowledges that save without another write. A missing/different row, lost lease,
failed observation, explicit provider denial or invalid response still fails closed.
The HTTP and per-operation deadlines remain unchanged; at most one extra read is
allowed, with no command replay, automatic process restart or permission restoration.
This does not recover a journal that has already latched unavailable: stop promotion
and preserve its history, lease and pending-work evidence under the existing recovery
controls before any separately reviewed recovery deployment.

Require an already-stopped, confirmed idle runtime before rollback; preserve unknown
active or proposed work and coordinate its owner rather than cancelling it to release.
Preserve the private journal and retain the stop latch.
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
