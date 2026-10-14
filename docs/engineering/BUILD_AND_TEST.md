# Independent software builds and tests

> Current pipeline: [automated review, staging qualification and owner activation](../development/CI_CD_PIPELINE_REPORT.md). Prepared local changes are not live deployments; branch/PR optimization and automatic technical evidence supersede older manual-only details.

Use the [frontend](../../onesa-ai-robot-frontend/README.md) and
[backend](../../onesa-ai-robot-backend/README.md) commands. Node 24 and Python 3.11
are qualified software runtimes. Both applications have independent Dockerfiles,
lockfiles and environment examples; sibling source is never a build dependency.

From the repository root, with the backend venv active, regenerate a deliberately
reviewed contract change with `python scripts/generate-contracts.py`, then from the
frontend directory `npx openapi-typescript contracts/openapi.json -o
contracts/schema.ts`. `python scripts/check-contracts.py` rejects accidental drift;
do not regenerate to erase a breaking change without compatibility review.

CI checks backend security/simulation/persistence, frontend builds/proxy/typed routes,
all three browsers at 320/390/768/1024/1440, dependency advisories, runtime image
vulnerabilities/secrets and publication hygiene. Candidate packaging requires all
exact-revision jobs. Generated runtime data/raw security reports stay private.

Scope: software simulation only. ROS 2 installed edge integration,
model endpoints, actual sensor/actuator behavior, emergency-stop hardware and real
edge-network latency remain NOT TESTED or BLOCKED until their targets exist.
Automated accessibility checks do not certify complete WCAG 2.2 AA compliance.

Release changes also require `.venv/bin/python -m unittest discover -s scripts/release
-p 'test_*.py'` from the root, `actionlint .github/workflows/*.yml`, and backend
`python -m mypy robot_api` with the hash-locked development requirements. ROS interface
verification uses the pinned official Jazzy image command in `scaffold.yml`, with no
external network. Keep all three browser projects required; local launch failure is
not a passing application test.


Appearance uses `node --test scripts/test_system_appearance.mjs` from the root;
repository documentation uses `python3 scripts/check_repository_docs.py` and
`python3 -m unittest discover -s scripts -p test_repository_docs.py`. The browser
suite tests both system preferences against contrary mocked local hours, public
root isolation, live preference changes with drafts/simulation and accessibility.
`ONESA_VISUAL_EVIDENCE_DIR` may select only a protected directory for synthetic
screenshots; never set it to public assets or include private test credentials.
The shared foundation digest is verified by the frontend build.

## Dependency maintenance

Automatic security-update PR creation is disabled under the owner's explicit
14 October 2026 authorization; Dependabot alerts remain enabled. The owner confirmed
receipt and review of Actions failure notifications and Dependabot alerts for this
repository. Existing security PRs and branches remain intact. Version-update config,
registry settings and compatibility constraints are retained with zero automatic PRs.
The existing full verification workflow runs weekly on Monday at 06:17 UTC after
this version reaches main; changes to dev, staging and main retain required checks.
Dependency/source and final-image scans are mandatory. A session is not a monitor.

Review alerts and preserve advisory, severity, affected version, remediation and owner
in the existing restricted findings register. Apply supported updates on dev, qualify
staging and main, then verify the deployed artifact. Never dismiss alerts or weaken
checks to make a release pass. Restore security-fix PR preparation only through an
authorized repository-level `automated-security-fixes` PUT operation. Direct graph
SBOM readback returned HTTP404; no dependency-graph setting was changed.
