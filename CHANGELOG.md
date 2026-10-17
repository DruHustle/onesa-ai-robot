# Changelog

## 2026-10-17 — Earlier journal renewal accepted in production

- Accepted candidate `632746daaf71c9f1785c35f7de95998fc50c3333` after fresh
  exact-main CI. Its full tree matches staging `295e80a`; the actual deployed
  backend remains identified as `f591af43b56417c43caf91620e00ec9e04b8b7e4`.
  The unchanged frontend remains `f83b401`, deployment
  `dpl_BbnqqJcwqqm9TSzhr35KJEpENnnD`; no redundant frontend deployment occurred.
- All 14 staging API checks and 96 browser cases passed. The separately approved
  read-only accounting continuation verified every prior record and all 36 new
  owned records. The original failed compound observer result is retained.
- Production operator sign-in, one owned simulation, Stop/logout and six private
  access denials pass. All 77 previous records are unchanged; the single completed
  test record brings history to 78. Credentials and the other eight services are
  preserved. A 180-second observation passed seven health/readiness samples, with
  no journal failure, restart or OOM. Physical operation was not performed.
- Renew the journal lease earlier so one uncertain acknowledgement can be
  reconciled while the prior lease still has the required freshness. Keep the
  two-second statement deadline, four-second confirmation budget, 30-second lease,
  18-second proof, 15-second readiness guard and no statement replay. Virtual-clock
  tests cover lost/committed acknowledgements, scheduler jitter and fail-closed
  late/foreign/repeated uncertainty. This does not promise uninterrupted provider
  connectivity; ownership, freshness and fail-closed behavior remain enforced.

## 2026-10-17 — Qualified Oracle Robot release live

- Released frontend `f83b401f3af46d1fdd3459aa8b622d947d825373`, deployment
  `dpl_BbnqqJcwqqm9TSzhr35KJEpENnnD`, with qualified Oracle backend source
  `3505bc270a5636347586dbe2542ccd35d6f85600`. The complete source trees are
  identical; the actual backend source is retained rather than relabelled.
- Full exact-main CI and staging passed all 14 API checks and 96 browser cases,
  with no skipped or flaky cases. Production sign-in, administrator controls,
  one software simulation, Stop/logout and six anonymous/spoofed-bot denials pass.
- Preserved all 76 existing production records and appended only one completed
  owned acceptance record. Credentials/runtime bytes and the other eight services
  are unchanged; all nine services are healthy in bounded post-release observation.
- Preserved original observer failures and their explicit reconciliations. No
  failed application test was overridden, old-source restart used, or hardware actuated.

- Align the gateway's bounded acknowledgement deadline with journal confirmation,
  below the existing client deadline; never replay uncertain mutations. Buffer a
  complete upstream body before forwarding success or session cookies, and emit
  fixed failure categories without credentials or private request details.
- Capture allowlisted page/static-asset timing alongside API timing on a failed
  browser case; keep navigation deadlines, completion checks and zero retries.
- Let journal HTTP reads use the existing two-second statement budget; keep
  the total deadline, one-read reconciliation, lease freshness and fencing unchanged.
- Keep anonymous browser fixtures away from protected session-cleanup endpoints;
  bound and verify logout/revocation when a test actually has an operator cookie.
- Reserve a bounded read-only confirmation budget after an uncertain journal lease
  renewal, without replaying the write or changing ownership/freshness checks.
- Correct the shared design guide link to the existing protected engineering host.
- Consolidate duplicate agent governance instructions while retaining release,
  credential, authorization and physical-controller safety requirements.

## 2026-10-16 — Protected Oracle VM operations documentation

- Added the shared VM layout, exact API routes/loopback ports, environment isolation,
  worker/scanner boundaries, Tailscale administration and resource limits.
- Linked read-only troubleshooting, monitoring, backup and recovery procedures from
  maintained deployment references; private runtime values and evidence remain excluded.
- Documentation changes do not deploy, restart or qualify an application.

## 2026-10-16 — Robot production API moved to Oracle

- Moved the existing qualified backend to an immutable, scanned ARM64 image on
  the existing Oracle Free VM, behind a dedicated HTTPS tunnel and loopback bind.
- Republished the identical accepted frontend artifact with its server-side API
  origin changed. Existing authenticated access, protected reads, logout/revocation
  and anonymous denial pass through the production website.
- Preserved accounts, credentials, external data and existing worker/scanner services.
  No Render build, paid resource, schema migration or physical actuation occurred.
- Prior full application qualification is reused for unchanged source; new target
  checks establish access and readiness, not a new feature or inference release.
  Staging Preview acceptance remains independently recorded in restricted evidence.


## 2026-10-15 — Robot development release live and accepted

Production frontend and cloud backend now serve
`595fd4f494e77de4fdecacbb9e64ac46c8c3597b` at https://robot.onesa.eu.
The under-development public product, concept artwork and protected operator console
are live. The designated existing administrator has password-confirmed, session-bound
allow/block controls for future physical-operation permission; controller connection,
readiness and actual actuation remain separate. No hardware is connected or actuated.

The release includes the reviewed journal transport/lease confirmation corrections,
originating-form handling and observation-ready simulator controls. Stop, cancel and
sign-out remain available independently. Exact-main staging passed 16 API/safety checks
and96 browser cases. Production acceptance passed 14 API/safety/admin checks, two public
layouts, anonymous console isolation and six ordinary/spoofed-bot private-data denials.
All 73 prior history fingerprints and credentials are unchanged; three synthetic terminal
acceptance records are retained and accounted for. A bounded post-deployment runtime
log window found no matched journal/error/HTTP 5xx categories.

Vercel deployment: `dpl_FX54UPw53gMQ1TL7sY2kMH71YfKW`.
Render deployment: `dep-db8g94o473hc73ert5h0`.
Existing publication observation was resumed without a duplicate deployment after a
whole-project metadata digest mismatch. The premature public CSS timing observation
and its corrected read-only continuation remain in restricted evidence. No failed
historical suite was rewritten as PASS. Development privacy records remain owner-deferred
until launch; this release does not claim legal certification or physical safety approval.


## 2026-10-14 — Frontend icons delivered; hosted acceptance blocked

Production frontend `56ce52f20ddf7a491de0b33a3805d0c02cc0d345` delivered the approved
Robot SVG/ICO/touch icon family and bounded sign-in readiness/manual recovery. The
independently qualified backend remained at `1638108`; no backend redeployment,
credential rotation or database provider change accompanied the frontend delivery.
Canonical API acceptance passed 13/13 and warm desktop/simulated-mobile loading passed.

The first production browser suite passed 80/81: Chromium 27/27, Firefox 27/27 and
WebKit 26/27. WebKit's light 768px flow did not return to the sign-in form after
Sign out within the existing five-second assertion. The failed suite is retained;
the inherited focused-form interaction defect is being corrected through a new
qualified release. The original failing click's focus was not recorded.

At 09:09 UTC, both canonical and direct backend readiness returned 503 with the
fixed journal-recovery category. Read-only checks preserved all 37 earlier record
fingerprints within the 73-record journal, found no running/proposed work and an
expired lease, and verified unchanged runtime configuration and credentials. The
underlying journal exception remains unproven. Overall production acceptance remains
BLOCKED; no automatic restart, rollback, history deletion or physical actuation occurred.

## 2026-10-14 — Shared design deployment; browser acceptance incomplete

Production source `16381086192dc34c8ad7ea40c43ef6d178b00904` deployed the public Robot
product, protected operator console and shared Onesa foundation with browser/OS light
and dark appearance. Production API/safety/edge checks passed 13/13, and provider source
identity, existing credentials and three earlier history records were verified.

Hosted acceptance at 03:46:09 UTC passed 67/69 browser checks; two initial Chromium
sign-ins returned 503 Gateway unavailable. Firefox and WebKit passed 23/23 each. The
mandatory browser gate remains FAIL and the overall acceptance receipt BLOCKED pending
a qualified recovery release. The failed suite remains in the restricted release
evidence store. Physical actuation remains disabled. No new icon assets are claimed
deployed by this revision.

## 2026-10-13 — Software simulation production baseline

First verified production go-live of the authenticated Onesa AI Robot software
simulator at https://robot.onesa.eu, source
`b0d40c6d2ccab2b1663166ebf311b4a9755ad045`.

Operator authentication, simulation proposals and approval, safety denial, stop and
cancellation, heartbeat loss, stale/replayed command rejection, task history, isolated
durable storage and synthetic edge telemetry passed hosted acceptance on
2026-10-13 at 20:03:33 UTC. Physical actuation remains disabled; hardware, perception
models and physical safety certification are outside this released scope.

The immutable source/artifact qualification, owner authorization and deployment
receipts are retained in the restricted release evidence store. Pre-launch setup
changes remain in Git history and internal engineering records. Subsequent release
entries are added only after verified production deployment.
