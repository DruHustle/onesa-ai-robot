# Onesa AI Robot

Independent Onesa UG robotics repository. This workspace started empty; this change
prepares engineering governance and application boundaries. A static frontend theme
preview is available; **no connected robot application or backend exists yet.**
No hardware operation is authorized.

| Directory | Intended application |
| --- | --- |
| `onesa-ai-robot-frontend/` | Independently deployable operator interface (planned) |
| `onesa-ai-robot-backend/` | Independently deployable robot gateway (planned) |

Keep robot-specific dependencies here. Consume the AI platform through authenticated,
versioned APIs; do not copy its Git history or require sibling source for builds.
Choose runtime, hardware targets, contracts and safety requirements before implementing.

[Build/test status](docs/engineering/BUILD_AND_TEST.md) · [Deployment plan](docs/engineering/DEPLOYMENT.md)
· [Engineering policies](AGENTS.md).
The root `.env.example` and application examples are proposed configuration, not a
working runtime contract. No license is assigned pending ownership approval.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Verified branch protection status](docs/development/BRANCH_PROTECTION_REPORT.md). Main protection is currently **BLOCKED — NOT ENFORCED** by GitHub plan eligibility.

The selected policy is [GitHub Free with private repositories](docs/development/FREE_GITHUB_PLAN.md). PR and check discipline is voluntary until server protection is supported; no upgrade or visibility change is proposed.
