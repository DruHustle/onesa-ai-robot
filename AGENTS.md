# Onesa engineering and agent policies

This is the single policy file for `onesa-ai-robot`, including Codex/agent instructions,
contribution rules, security reporting and repository governance. Keep policies here;
do not recreate separate setup, implementation-status or session-handoff documents.
Read README, current release checklist, architecture and code before editing.
Continue incomplete work without restarting implemented features.
Update the changelog, contracts and affected operational documentation when behavior
changes. Record unverified functionality honestly in the applicable release checklist
or roadmap. Explicit user instructions and previously authorized scope take precedence.
Preserve local modifications, history and data; stage only reviewed paths.
Use free services only; do not provision paid resources or accept paid upgrades
without explicit budget authorization.

## Contribution rules

Keep this repository independent within `onesa-ug`: retain component directories,
separate releases and no workspace Git repository or sibling submodules.

Keep exactly three permanent branches: `dev`, `staging`, `main`. Normal integration
is `dev → staging → main`. Temporary Dependabot security-update PR branches and
necessary narrowly scoped security-release candidates are authorized exceptions,
not permanent branch families. Ordinary version-update PRs remain disabled. See the
security integration procedure in `docs/engineering/CI_CD.md` before using an exception.
Preserve work already staged or modified locally. The verified team currently has one
developer: require PRs and automated checks, with zero independent approvals until
an authorized reviewer exists. Then require one independent review; seek two for
authentication, personal data, infrastructure or robot actuation when available.
Describe the problem, resulting behavior, validation and deployment/rollback impact.
Update API contracts, migrations and documentation with behavior changes.

Run the commands in `docs/engineering/BUILD_AND_TEST.md` and
`python3 scripts/repository_hygiene.py` before staging. Inspect `git diff --cached`
and `git status --short`. Never stage private records, uploads, dumps, models or secrets.
Use synthetic fixtures; a private repository is not a secret store. Keep environment
examples as placeholders. New dependencies need provenance and license review.
Do not introduce a project license until ownership and licensing are approved.

Application builds and releases are independent. Changes to a shared contract must
remain compatible during separate rollouts. Production promotion, remote pushes and
visibility changes require explicit authorization. See `docs/engineering/DEPLOYMENT.md`. Actual protection status and activation prerequisites are recorded in
`docs/development/BRANCH_PROTECTION_REPORT.md`; reverify remote enforcement after visibility changes.

## Security policy

Supported software: the latest reviewed revision of `main`; no historical release
support promise is made before a release/support policy is approved.

Report vulnerabilities privately through GitHub's private vulnerability reporting
if enabled, or an organization owner using an existing private channel. Do not file
credentials, customer records, exploitation details or personal data in public issues.
The approved private reporting contact is info@onesa.eu; do not invent a security mailbox, bounty or response guarantee.

Do not store API credentials, production environment files, private corporate records,
model weights, database dumps or user uploads in Git or CI artifacts. Use a secret
manager and access-controlled storage. Separate frontend public configuration from
backend secrets. Local `.env` files must remain ignored; examples contain placeholders.
Use least-privilege database/service identities and protected production environments.

If a credential was committed, revoke/rotate it first, assess access and logs, and
notify the security owner privately. Ignoring or untracking a file does not remove
it from history. Remove it from future commits only after reviewing staged work;
historical removal requires a separately approved, coordinated remediation plan.
Never automatically rewrite history or force-push. Confidential documents already
in history block publication until an owner approves an appropriate remediation.

`python3 scripts/repository_hygiene.py --history` scans available reachable history,
staged content and publishable working files without printing matched values.
This heuristic cannot prove absence of secrets or confidential prose. Enable GitHub
secret scanning/push protection where the organization plan supports it, and conduct
human data-classification review before publishing or uploading CI artifacts.

## Repository governance

### Visibility, runner selection and access

The current owner request selects private GitHub Free safeguards. Credential-free
PR checks use GitHub-hosted runners within the free private quota; a local runner
must not be a mandatory dependency for untrusted PR validation. Keep the retained
private-only reusable runner dormant unless separately isolated and authorized.
Production credentials must be held outside editable repository Actions. Repository
writers can alter workflows to read repository secrets; restrict write access.
Readback on 2026-10-11 still returned public and account plan null. Do not change
visibility, billing, ownership, access or provider settings without authorization.
See `docs/development/PRIVATE_FREE_SAFEGUARDS.md` for scope and owner actions.

### Protect main

These repositories remain personally owned by DruHustle. Earlier HTTP 403 protection
failures occurred when they were private; do not treat them as evidence of current
public eligibility or enforcement. The runner change does not activate protections.
Inspect actual remote rules before claiming server enforcement. See
`docs/development/BRANCH_PROTECTION_REPORT.md` for historical evidence and exact CI
contexts. Keep PR/check/review discipline and all production authorization gates.

The prepared main policy requires PRs, resolved conversations and observed CI/security
checks with no routine bypass. Zero independent approvals reflects the current solo
maintainer; raise review requirements only after a real reviewer is authorized.
Do not drop failed checks or invent required jobs. Emergency recovery is a recorded,
temporary authorized policy correction. Actual provider/production/preview credential
controls remain separate from branch protection and require their own verification.

Sources: [GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets),
[secret scanning availability](https://docs.github.com/en/code-security/how-tos/secure-your-secrets/detect-secret-leaks/enable-secret-scanning),
[GitHub CLI repository creation](https://cli.github.com/manual/gh_repo_create).


## Selected GitHub Free policy

Follow `docs/development/FREE_GITHUB_PLAN.md` and the private-Free safeguard report.
Native private-Free branch/environment protection is unavailable. Direct pushes remain
possible; CI and qualification block only the authorized deployment path. Private
production uses credential-free owner authorization and externally controlled promotion.
Retain exact-commit security/staging checks and separate hardware authorization. Do
not claim remote safeguards are active until the owner completes and verifies migration.

## Current automated CI/CD policy

Use dev PRs to staging, then qualified staging PRs to main. Prior acceptance branch commits are preserved in restricted recovery bundles; do not recreate remote branches without owner authorization.
Reviewdog annotations are read-only CI evidence, not an independent human review.
The mandatory security/summary checks and full exact-main runtime records are release
requirements. Automatic staging is private-only and default-off pending scoped targets;
production credentials remain outside editable repository Actions. See
[the pipeline report](docs/development/CI_CD_PIPELINE_REPORT.md) for tested limits,
reviewed workflow_run exceptions, owner actions and remote activation status.

## Product, appearance and Code Review Rules

The public product at `/` is script-free and never reads operator data. `/console`
loads only the authenticated simulator API; menus and hidden markup are not access
controls. Preserve the single configured operator and existing credentials, device
bearer isolation, object ownership, expiring proposals, session/heartbeat revocation,
independent software motion gate and permanently disabled physical actuation.
Do not add hardware control, public DDS or automatic task replay. Real model/ROS/
hardware capability must never be presented as a synthetic fallback.

Follow the versioned Onesa design contract in `docs/engineering/design-system.consumer.json`
and its protected guide. Shared foundations preserve Robot's product identity and
operational hierarchy. Appearance follows `prefers-color-scheme` through CSS; no
clock schedule, selector, appearance cookie or stored override. Mode changes must
preserve focus, drafts, authentication and simulation execution. Environment labels
come from trusted runtime configuration; simulation/live labels come from actual data.

Code review prioritizes authorization/object access, stop/freshness/replay behavior,
private telemetry, task cancellation, storage/lease integrity, secret handling,
contract compatibility and release provenance. Distinguish a demonstrated regression
from a hypothesis; avoid duplicate style remarks. Use parameterized SQL, bounded
validation/timeouts/retries, UTC events, minimal redacted logs and locked dependencies.
Never weaken a failed mandatory check, hand-edit generated contracts, upload code to
an unapproved reviewer or assert independent approval of your own implementation.

## Local command matrix and definition of done

| Task / directory | Command | Prerequisites, environment and effect |
| --- | --- | --- |
| Frontend install / frontend | `npm ci --ignore-scripts` | Node 24; local locked dependency installation |
| Frontend verification / frontend | `npm run lint && npm run build && npm run typecheck && npm test` | Installed locks; local generated client/build; unit tests bind loopback |
| Backend install / backend | `python3.11 -m venv .venv && .venv/bin/python -m pip install --require-hashes -r requirements-dev.lock` | Python 3.11; isolated local environment, no provider credentials |
| Backend verification / backend | `.venv/bin/python -m ruff check robot_api tests && .venv/bin/python -m ruff format --check robot_api tests && .venv/bin/python -m mypy robot_api && .venv/bin/python -m pytest -q` | Backend venv; isolated synthetic fixtures only |
| Contract / root | `python scripts/generate-contracts.py && python scripts/check-contracts.py` | Active backend venv and Node 24; source-generated schema/types |
| Appearance / root | `node --test scripts/test_system_appearance.mjs` | Node 24; offline shared digest/system-preference/public isolation checks |
| Repository docs / root | `python3 scripts/check_repository_docs.py` | Offline root policies, references and true release-baseline checks |
| Browser / frontend | `npm run test:e2e` | Isolated simulator and three installed browsers; synthetic account, no live hardware |
| Hygiene / root | `python3 scripts/repository_hygiene.py` | Read-only source/index scan; private values are never printed |

The backend README defines secure local environment startup. The root README and
onboarding define the smallest local path; provider/recovery procedures belong in
protected engineering docs. Installed dependencies are not proof of a clean-room
setup. Record the actual environment/result for every check, including missing
browser/device/resource blockers. Deployment is not a safe local test default.

Before risky work read DEPLOYMENT, AUTOMATED_QUALIFICATION, SIMULATION_ARCHITECTURE
and the current restricted release evidence. Current user authorization can permit a
qualified release but never proves tests or extends blanket authority to future sessions.
Coordinate branches, schemas and provider writes; retain recovery and existing data.
Done means reviewed source, safe cleanup, passing affected checks, accounted evidence
and verified authorized hosted scope. Report the exact genuine blocker and next
executable action. Only verified production changes enter the root CHANGELOG.

Dependency maintenance retains alerts, scans, scheduled CI and owner-confirmed
notifications. Authorized Dependabot security PRs target the unchanged default main;
version `target-branch: dev` cannot retarget security fixes. PR code runs credential-free
on GitHub-hosted runners, with no auto-merge, privileged PR event or automatic production.
A bot label/branch name is not qualification. Normally carry the reviewed fix through
dev/staging/main. If unfinished dev must be excluded, start the smallest temporary
security candidate from the exact deployed production SHA; obtain owner-controlled
staging and exact-source qualification before any release, then reconcile dev/staging.
Keep existing release and runner guards. Delete a temporary branch only after proven
incorporation, retained evidence and active-review/work checks; never bulk-delete bots.
