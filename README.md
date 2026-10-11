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
· [GitHub setup](GITHUB_SETUP.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md).
The root `.env.example` and application examples are proposed configuration, not a
working runtime contract. No license is assigned pending ownership approval.

Actions visibility, local-first private validation and hosted public routing: [runner maintenance](docs/engineering/SELF_HOSTED_RUNNER.md).
