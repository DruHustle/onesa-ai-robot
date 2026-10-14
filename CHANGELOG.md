# Changelog

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
