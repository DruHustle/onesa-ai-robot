# Changelog

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
