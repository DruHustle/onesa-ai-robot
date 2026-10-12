# Changelog

## 2026-10-12 — Private staging credential diagnostics

Report whether the named Preview automation bypass reaches the direct Staging inspection job as a boolean. Secret-name inventory alone does not establish a usable value or reusable-workflow binding. Preserve the existing operator credentials; reconcile the authorized test secret privately, without resetting the operator or weakening Preview protection.

## Staging branch and environment configuration

- Standardize remote branches on dev, staging and main; preserve branch history in restricted recovery bundles.
- Scope staging workflows to the GitHub Staging environment and retain commit-specific production authorization.
- Use each product’s existing Vercel project for staging previews; enable Git previews only for staging in the prepared configuration.
- Document required environment secret names and block missing or excessively privileged credentials.


## 2026-10-11 — Turso staging task persistence

- Add an explicit staging-only remote task journal over authenticated HTTPS, with
  bounded nonblocking requests, parameter binding, redacted failures and fenced
  single-writer ownership. Keep local SQLite and its application-thread ownership.
- Restore task history, revoke process-local sessions, latch stop and cancel
  unfinished work on restart. Cloud failure stops simulation and fails readiness;
  recovery requires restart, without silent local fallback or command replay.
- Bound readiness to recent background lease proof; anonymous probes cannot
  exhaust the remote connection pool.
- Persist accepted task events rather than writing telemetry at the 20 Hz tick rate.
  Local watchdog/stop controls remain independent of cloud latency. Recheck approval
  authority after storage acknowledgement; reject a reset raced by a newer stop.
- Add isolated real-SQL/HTTP-protocol regression tests and exact staging-storage
  bindings in the controlled release preflight/smoke workflow. Production and
  physical-actuation guards remain intact. Actual hosted Turso verification pending.

## 2026-10-11 — Preserve audited applications with owner runner policy

- Merge the owner-approved main policy without replacing current application fixes.
- Public jobs verify hosted execution and live visibility; private reusable validation
  retains all implemented tests, browser matrices, startup and image-security gates.
- No local runner activation, production promotion or physical control.

## 2026-10-11 — Public repository hosted Actions

- Make browser setup fail when password hashing or backend readiness fails; retain
  all three browser suites and bound startup waiting.

- Record the owner-selected temporary public visibility and standard GitHub-hosted
  runner policy. Local runners remain private-only; retain security and release gates.
- Clarify that earlier private-plan protection failures are historical and do not
  establish current public-repository enforcement. No billing or protection settings changed.

## 2026-10-11 — Incomplete request deadline

Bound simulator mutation body reception to five seconds total and reject excess
bytes before concatenation. Stalled and trickling ASGI request regressions verify
408/no-store; existing Origin, session, CSRF and physical-actuation gates remain.

- Record owner-created Robot Render targets and their unverified state. Free-tier persistent-storage and hosted simulator acceptance remain blocked; no physical or public promotion is enabled.

## 2026-10-11 — Private staging host instructions

Documented separate simulator containers, a dedicated private network with the
frontend's accepted backend alias, persistent non-root storage and private operator
credentials on an existing host. Loopback-only exposure, restart/recovery acceptance
and permanently disabled physical actuation remain explicit. No cloud deployment is
inferred; Render Free's ephemeral storage is unsuitable for this SQLite gateway.

## 2026-10-11 — Authenticated software simulator candidate

Preserved the Onesa visual identity and added separate FastAPI simulation and static
operator applications, durable synthetic task history, scoped sessions/CSRF, explicit
operator approval, independent motion limits, cancellation, stop/reset, watchdog and
safe restart. Added generated versioned API types, ROS 2 preparatory messages,
reproducible locks, non-root images and software/security/browser CI gates.
Physical actuation and real model/ROS/hardware readiness remain unavailable.

Watchdog loss also rejects reset/proposal/approval, password confirmations are
rate-limited independently, startup validation hides secret inputs, and shutdown
closes storage even after a watchdog failure.

## 2026-10-11 — Password work and watchdog isolation

Move scrypt verification off the simulation event loop with two bounded concurrent
slots. Busy callers fail with 429; a cancelled caller retains its slot until hashing
finishes. The watchdog and stop route remain responsive during slow password work.
Approval/reset recheck watchdog and session authority after confirmation yields.
Regressions cover heartbeat loss during hashing, capacity after cancellation and
concurrent logout during task approval. Physical actuation remains disabled.

The operator UI also ignores failures from obsolete telemetry requests after a
new session is established. A browser regression delays an old 401 across sign-out
and sign-in and verifies that the new session remains authenticated.

## 2026-10-11 — Simulator SQLite connection ownership

- Enforce application-thread ownership of the simulator connection. Synthetic expiry,
  stale-proposal and owner edits, plus online backup fixtures, run through the
  application portal so watchdog commits cannot overlap a caller-thread transaction.
- Preserve all session, cancellation, restore and safety assertions; add a regression
  proving foreign-thread SQL is rejected while readiness remains available.

## 2026-10-11 — Remote CI integration review

Removed pip caching from the publication hygiene job because it installs no packages; GitHub runner cleanup otherwise fails when the cache directory is absent.

## 2026-10-11 — Owner release configuration inspection

Added an owner-only manual, read-only hosting diagnostic to verify the existing Robot production/staging targets and redacted variable presence. It cannot deploy or enable actuation; no provider credentials are exposed to PR jobs. Private Free production credential migration remains required.

Hosting inspection is isolated in its own manual workflow; PR validation stays entirely credential-free. The new workflow becomes dispatchable after reviewed main integration.
