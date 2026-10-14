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

The current browser matrix is 84 cases: 28 each in Chromium, Firefox and WebKit,
with no skipped/flaky cases or automatic retries. The pending-form interaction
fixture uses test-owned HTTP responses and no backend mutation; it requires Stop
and Sign out to remain usable while an unrelated form response is pending. Existing
operator, authorization, appearance and accessibility cases remain required. Offline
module tests prove independent Stop/cancel/logout and duplicate originating-form
suppression. Submission scope comes from the synchronous event currentTarget;
focused controls do not determine which independent action may run.

## Dependency maintenance

The owner's latest 14 October 2026 instruction authorizes temporary Dependabot
security-update PR branches and necessary narrowly scoped security-release candidates,
while retaining exactly three permanent branches: dev, staging and main. It supersedes
the earlier same-day security-PR disable instruction. The owner confirmed receipt and
review of Actions failures and Dependabot notifications. Alerts, dependency/source and
final-image scans, existing security PRs and evidence remain intact. The root coordinating
session restores and verifies the separate repository security-fix setting; a source
configuration alone does not prove the remote setting is active. Read-only API
metadata at 2026-10-14 01:25 UTC returned `enabled: true`, `paused: false`;
default main and the existing open dev-to-staging PR were preserved.

Ordinary version PRs remain disabled with `open-pull-requests-limit: 0`. Their retained
configuration targets dev. Security updates always target the unchanged repository
default main; target-branch does not redirect security fixes, and version-only groups/
cooldown settings do not constrain them. No auto-merge or automatic production release
is enabled. Review fixes through [the security integration procedure](CI_CD.md#security-pr-integration-and-urgent-candidates).

The existing full verification workflow runs weekly on Monday at 06:17 UTC once this
version reaches main; dev/staging/main changes retain required checks. Temporary security
PR code receives credential-free GitHub-hosted PR checks targeting a permanent branch;
never send it provider secrets or a persistent privileged runner. A scheduled scan or
Actions session does not itself establish delivered monitoring.

Review alerts and preserve advisory, severity, affected version, remediation and owner
in the existing restricted register. Normally apply reviewed fixes on dev and qualify
staging/main; necessary urgent candidates start from exact production and exclude
unfinished dev work. No alert dismissal, check suppression, credential rotation or
branch deletion is implied. Direct graph SBOM readback previously returned HTTP404;
no dependency-graph setting was changed by this source update.
