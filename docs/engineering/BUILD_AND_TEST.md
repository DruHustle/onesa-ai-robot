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

## Bounded sign-in acceptance

After submitting Sign in, browser scenarios use `waitForOperatorSignIn`: the same
25-second acknowledgement bound already used by the main simulation journey.
The application checks readiness for at most 15 seconds before its 10-second
credential request. A default five-second assertion can expire before login starts.
Ordinary layout, simulation, request and safety deadlines remain unchanged.

Reload and late-response regressions observe the existing session/logout HTTP
acknowledgement within the client's existing 10-second request budget before
checking the resulting UI with its unchanged assertion deadline. They issue no
extra request and require HTTP 200 with CSRF or `signed_out` as appropriate.
Offline tests retain failure behavior for missing fields, 401/403/503 and timeout;
cleanup diagnostics expose only HTTP status, never bodies or credentials.

`tests/browser/sign-in-readiness.spec.mjs` intercepts every API request with synthetic
responses. It holds readiness unavailable beyond five seconds, verifies that no
credentials are sent, then permits readiness and requires one login, cleared password
input and zero task/control mutations. Its local three-engine result does not replace
source-bound hosted qualification or authorize retrying a failed context.

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

The source browser matrix is 90 cases: 30 each in Chromium, Firefox and WebKit,
with no skipped/flaky cases or automatic retries. The pending-form interaction
fixture uses test-owned HTTP responses and no backend mutation; it requires Stop
and Sign out to remain usable while an unrelated form response is pending. Existing
operator, authorization, appearance and accessibility cases remain required. Offline
module tests prove independent Stop/cancel/logout and duplicate originating-form
suppression. Submission scope comes from the synchronous event currentTarget;
focused controls do not determine which independent action may run.

Browser cleanup checks for the test context's host-scoped operator cookie before
requesting protected session endpoints. Anonymous public and intercepted fixtures
make no cleanup API calls. An existing session requires bounded session read,
CSRF-protected logout and confirmed revocation; unavailable cleanup fails rather
than silently passing. `node --test tests/session-cleanup.test.mjs` from the
frontend verifies these boundaries without a browser, account or network target.
Failed browser cases now retain bounded request-start, response-header, completion,
transport-failure and document-lifecycle events, plus requests still pending when
failure is reported. This closes the earlier diagnostic gap where a stalled request
could leave an empty timing log. Only known same-origin route labels, masked task
identifiers, methods, statuses and elapsed times are recorded; headers, bodies,
query strings, arbitrary paths and credentials are excluded. Five isolated recorder
regressions cover stalled navigation, terminal events, redaction and memory bounds.
An isolated Firefox control and GET-only public console observation passed on
17 October; API requests were blocked. That observation does not qualify the failed
Preview or establish the cause of its earlier navigation timeout.

The public navigation, image, isolation and accessibility assertions and their
timeouts are unchanged. This corrects an observed anonymous cleanup-hook timeout;
it does not establish the cause of a separate hosted navigation transport timeout.

The six new administration cases use isolated, test-owned API responses to verify
the permission form, role visibility, OS-preference focus preservation and accessible
state labels. Backend `tests/test_physical_permission.py` exercises actual authorization,
Origin/CSRF, password/revision checks, concurrent Block/Stop, expiry and logout.
The real API/safety smoke requires `administrator_operation_permission`: the designated
staging administrator must actually allow then block permission while hardware stays
unconnected/inactive and task history stays unchanged. The previous 84-case hosted
result cannot qualify this new source; local Firefox launch failures stay explicit
until the new source passes Firefox in CI and hosted staging.

## Dependency maintenance

The 20 October 2026 audit detected critical
[GHSA-6q48-6c7w-9gw2](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2):
certifi 2026.7.22 is affected; the reviewed source remedy is 2026.10.19. Andrew Gotora
owns remediation in the existing restricted findings register. Preserve the original
failed CI and any Dependabot advisory/PR references. Updated locks/audits are fix
preparation, not deployed verification: qualify the backend candidate, rebuild its
image and read back the installed version and trust store after release. Keep TLS
hostname/certificate validation, scans and owner-controlled dev/staging/main promotion.
Do not dismiss the finding or describe production as patched merely because a lock
or default-branch alert changed. No unrelated dependency upgrade is included.


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

## Safe acceptance failure evidence

The hosted observer keeps the failing phase and distinguishes unexpected HTTP
status, invalid JSON, timeout, DNS, TLS and socket failures using fixed categories
and bounded numbers only. It retains no URLs, error text, response bodies or credentials.
A transport failure is never a passing assertion or a confirmed application defect.
Expected replay denial still requires HTTP409 and valid JSON; timeouts, assertions,
mutation counts and retry limits are unchanged. Use the existing bounded repair
authority before another failed-context attempt.


## Bounded journal connection reuse

The Turso transport retains at most two healthy HTTPS connections for ten idle
seconds. This avoids a new TCP/TLS handshake for every five-second lease renewal.
It does not retry ambiguous statements or extend the two-second statement/seven-second
renewal budgets. Expired/disconnected idle sockets are discarded before sending;
a read/write failure after send remains a failure and never replays the statement.
Mock socket tests exercise healthy reuse, idle expiry, server disconnect and a
lost acknowledgement on an already reused connection. Hosted qualification is
still required; four staging SELECT1 samples establish overhead, not an uptime guarantee.


## Conditional journal recovery after a dropped connection

Task persistence compares the current record with its last acknowledged snapshot
inside the same owner-fenced UPSERT. An identical desired snapshot is idempotent;
a delayed older request cannot replace a newer acknowledged state. No schema or
existing history rewrite is required. After RemoteProtocolError only, an exact
read of the prior state (or an absent new ID) permits one conditional retry using
the same task ID and payload. Unknown/changed/missing known history, unavailable
confirmation, ordinary timeouts and explicit provider denials remain failures.
Each HTTP statement still has two seconds; total task-save recovery is bounded at
eight seconds, below the unchanged browser request deadline. Lease ownership,
renewal deadlines and safety/readiness limits remain unchanged. Real SQLite tests
cover late request ordering, committed/uncommitted acknowledgements, restored
snapshots, conflict, missing history and exhaustion. This is not an API command
replay or a promise to detect privileged out-of-band database tampering.


## Hosted completion observation

The simulation observer retains its original15-second total completion budget
(9s durable running acknowledgement plus6s history assertion). It starts observing
the existing GET task response immediately, requires the exact owned task to be
completed, then applies the unchanged6s DOM assertion within the remaining total.
It sends no extra request, retries no command and changes no browser30s test,
client10s request or backend safety/watchdog deadline. A real delayed response
control distinguishes this sequencing correction from an application failure.
Unknown/unauthorized/malformed responses and another task never satisfy it.
