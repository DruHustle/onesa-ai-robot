# Engineering changelog

## 2026-10-11 — Visibility-aware Actions policy

- Public repositories use hosted execution with zero local registration access; the former portal service was removed and its VM/login startup stopped. Repository visibility was not changed.
- Private workflows use a shared exact-revision local validation phase before cloud checks, preserving existing check names and release approvals. Runtime visibility hooks deny public/missing-token/API-failure execution independently of workflow conditions.
- Public cloud CI results and private unverified activation limitations are recorded in the runner maintenance guide after verification. Production remains gated.

- CI-only migration retains production gating by disabling automatic Vercel Git
  deployments at the scaffold root and frontend root. No provider release invoked.
