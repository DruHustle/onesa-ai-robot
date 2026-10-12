# Engineering changelog

## 2026-10-12 — Visitor-time appearance and protected staging deployment bridge

- The simulation interface supports persisted Auto/Light/Dark at visitor-local 07:00/19:00 boundaries, including blocked storage and mobile controls. Both-mode simulation/a11y coverage now spans all five viewport widths.
- Owner-hosted `release-candidate.yml` dispatches `inspect-staging`, `repair-staging` and `staging` against the retained staging branch. This registered workflow avoids requiring an unqualified main merge solely to register new workflow files.
- Staging inspection confirmed that the existing Free/Frankfurt service uses native Python and the approved Turso journal. Staging now accepts only the reviewed hash-locked dependency command and single-process startup, pinned to the locally qualified Python 3.11.14. Repair changes branch/root/health/runtime commands and disables automatic deployment; it preserves credentials, database records, production and physical permissions. Production retains its stricter Docker/storage gates.
- Staging receipts retain FAIL/BLOCKED results and only attest browser success from actual successful steps. Production durable-storage/hardware gates remain unchanged. The existing Turso adapter is preserved.
- Local backend: 42 simulation tests pass; release guards and history/security scans pass. Updated official immutable Node 24-compatible Actions. Hardware and external capabilities remain unqualified until real authorized evidence exists.

## 2026-10-11 — Visibility-aware Actions policy

- Public repositories use hosted execution with zero local registration access; the former portal service was removed and its VM/login startup stopped. Repository visibility was not changed.
- Private workflows use a shared exact-revision local validation phase before cloud checks, preserving existing check names and release approvals. Runtime visibility hooks deny public/missing-token/API-failure execution independently of workflow conditions.
- Public cloud CI results and private unverified activation limitations are recorded in the runner maintenance guide after verification. Production remains gated.

- CI-only migration retains production gating by disabling automatic Vercel Git
  deployments at the scaffold root and frontend root. No provider release invoked.

Staging device identity is copied only from the verified provider into a 0600 candidate-bound runner file, reused for the synthetic challenge, and removed after acceptance; no identity or credential is exposed in artifacts.
