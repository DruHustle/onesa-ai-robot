# Engineering changelog

## 2026-10-12 — Visitor-time appearance and protected staging deployment bridge

- The simulation interface supports persisted Auto/Light/Dark at visitor-local 07:00/19:00 boundaries, including blocked storage and mobile controls. Both-mode simulation/a11y coverage now spans all five viewport widths.
- Owner-hosted `release-candidate.yml` dispatches `inspect-staging`, `repair-staging` and `staging` against the retained staging branch. This registered workflow avoids requiring an unqualified main merge solely to register new workflow files.
- Staging configuration inspection/repair binds the existing Free/Frankfurt Docker service and approved Turso origin. Repair changes only branch/root/health/Docker layout and disables native deployment; no credentials, database, production target or physical permission changes.
- Staging receipts retain FAIL/BLOCKED results and only attest browser success from actual successful steps. Production durable-storage/hardware gates remain unchanged. The existing Turso adapter is preserved.
- Local backend: 42 simulation tests pass; release guards and history/security scans pass. Updated official immutable Node 24-compatible Actions. Hardware and external capabilities remain unqualified until real authorized evidence exists.

## 2026-10-11 — Visibility-aware Actions policy

- Public repositories use hosted execution with zero local registration access; the former portal service was removed and its VM/login startup stopped. Repository visibility was not changed.
- Private workflows use a shared exact-revision local validation phase before cloud checks, preserving existing check names and release approvals. Runtime visibility hooks deny public/missing-token/API-failure execution independently of workflow conditions.
- Public cloud CI results and private unverified activation limitations are recorded in the runner maintenance guide after verification. Production remains gated.

- CI-only migration retains production gating by disabling automatic Vercel Git
  deployments at the scaffold root and frontend root. No provider release invoked.
