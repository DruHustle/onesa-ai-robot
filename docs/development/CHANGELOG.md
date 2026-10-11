# Development changelog

## 2026-10-10 — GitHub Free governance plan

- Selected private GitHub Free operation with voluntary feature-branch PRs, verified
  CI, manual authorization and least practical write access. No paid upgrade or
  visibility workaround is proposed; main enforcement remains blocked.

## 2026-10-10 — Branch protection and governance audit

- Verified private personal ownership, admin access, actual PR CI/security check names
  and deployment/environment evidence across all three repositories.
- Attempted repository rulesets and classic fallback; GitHub rejected both with HTTP
  403 requiring Pro eligibility. Main readback remains unprotected, NOT ENFORCED.
- Prepared exact payloads, solo-developer PR/recovery policy, templates and API-backed
  reports. No workflow changes were needed for required check uniqueness.
- Existing local work is preserved. No push, merge, deployment, billing, visibility,
  credential or external provider change was performed.


## 2026-10-11 — Reviewed governance integration

Consolidated policy references and templates, preserved later audited runtime fixes, and reconciled deployment notes with actual staging evidence. Prepared protection settings remain reference only under GitHub Free. Original local work and private environment files are preserved. Public production qualification is unchanged.

## 2026-10-11 — Request-boundary simulation watchdog

CI exposed a delayed background watchdog leaving an expired task active at a status request. Authenticated requests now enforce task/session deadlines before reading state or refreshing a heartbeat. Session validation runs on the same event loop as simulation transitions; a failed watchdog revokes active authority. Two deterministic stalled-watchdog regressions cover status and late heartbeat, including frozen position and durable cancellation. All 15 backend tests and contract checks pass locally. Physical actuation remains disabled.
