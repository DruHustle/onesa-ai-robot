# Changelog

## Unreleased

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
