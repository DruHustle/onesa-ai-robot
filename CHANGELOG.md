# Changelog

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
