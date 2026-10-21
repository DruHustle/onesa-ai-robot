# Onesa AI Robot

Node application startup has a narrowly scoped CA trust policy, with isolated
regressions in `node --test scripts/test_tls_trust.mjs`. Use Node 24.12+ in the 24
series. Source implementation is separate from the accepted component releases
recorded below; no production update follows merely from merging source.

Production API hosting moved to the existing Oracle Free VM on 2026-10-16; the
Vercel frontend and existing data services remain. See the
[verified hosting cutover](docs/engineering/DEPLOYMENT.md)
for source identities, protected ingress, acceptance and rollback.

Onesa UG's robotics software development line. The current production scope is an
**authenticated software simulator**: propose a synthetic joint movement, confirm
operator approval, inspect task history, cancel or stop, and test safe failure behavior.
Physical actuators, connected ROS nodes, cameras and real STT/VLM/TTS/VLA models are
not implemented. Simulation results do not certify physical robot safety.

**Under development.** Protected operator access supports authorized development
and testing. Essential sign-in sessions, operator-linked synthetic task history and
security diagnostics support that purpose. The owner has deferred the corresponding
privacy approval records until launch; that decision is not a legal certification.
See the [scoped development release procedure](docs/engineering/DEPLOYMENT.md).

Latest accepted public frontend `ca1a0a54e51eb039f5bd8c39442a49ab55d5665b`, Vercel
`dpl_EXpzMcMmmhrNnVnqU9PcqaYzBFAJ`, serves `https://robot.onesa.eu/`. Its development
privacy notice now names the existing encrypted Neon recovery-storage recipient.
Full exact-main CI, 12 affected staged privacy views and four canonical privacy
accessibility/reflow views pass; readiness is200 and anonymous private status401.
The public product/image/CSS and operator runtime are unchanged from accepted
frontend `b6b6b10f474b0ccfbeb083ef3ace31964740225b`, whose 24 staged/eight canonical
public views remain separate evidence. The subsequent backend-only release uses
`d6e50fd01a1690167c1fbecb5ad995559b56e971`, qualified under main
`41bce7f35017f4d755372a13da57fd720f4bff33`. All188 backend tests,14 API checks
and111 distinct browser cases pass through preserved composite evidence. Production
acceptance verifies seven readiness samples, protected operator access/logout and all78
unchanged history records. The installed certifi2026.10.19 trust bundle is verified.
Bounded idle-only fenced recovery never resumes tasks or physical operation; no
single-host availability guarantee is implied. No production tasks or account/password
changes accompanied this backend release. See
[CHANGELOG.md](CHANGELOG.md) for accepted components and limits.


The public [Robot product](https://robot.onesa.eu) explains that scope. The operator
console serves protected simulation data through an independently authenticated API;
an ordinary Onesa AI account grants no Robot operator permission. In the earlier
2026-10-15 release, frontend and backend source
`595fd4f494e77de4fdecacbb9e64ac46c8c3597b` passed exact-main CI, hosted staging
(16 API/safety checks and 96 browser cases), current owner authorization and production
acceptance on 2026-10-15. Production verification passed 14 API/safety/administrator
checks, two public layouts, anonymous console isolation and six private-data denials.
All 73 pre-existing history records and credentials were preserved; three owned synthetic
acceptance records are accounted for. The service finished stopped/idle with no connected
controller or physical actuation. Current receipts and earlier failed observations are
recorded in [CHANGELOG.md](CHANGELOG.md) and [the protected deployment guide](docs/engineering/DEPLOYMENT.md).
Local or later source changes require their own applicable release verification.

```mermaid
flowchart LR
  Public[Public product and development privacy] --> Website[Robot frontend]
  Operator[Authorized operator] --> Gateway[Same-origin gateway]
  Gateway --> API[Authenticated simulation API]
  API --> Safety[Independent software gate and watchdog]
  API --> History[Private task journal]
  Safety --> Simulation[Synthetic joint only]
```

| Component | Technology | Local guide |
| --- | --- | --- |
| `onesa-ai-robot-frontend/` | Static HTML/CSS, generated TypeScript client, Node 24 proxy | [Frontend](onesa-ai-robot-frontend/README.md) |
| `onesa-ai-robot-backend/` | Python 3.11, FastAPI, local private SQLite; cloud Turso journal | [Backend](onesa-ai-robot-backend/README.md) |
| `edge/` and `ros2/` | Optional synthetic telemetry; preparatory ROS 2 Jazzy messages | [ROS boundary](ros2/README.md) |
| `docs/engineering/` | Architecture, tests, onboarding and release procedures | [Start here](docs/engineering/ENGINEERING_ONBOARDING.md) |

Use Python 3.11 and Node 24. For the smallest local setup, install the backend's
hash-locked development requirements into a virtual environment, generate a private
operator password hash, and configure an ignored environment file from its
`.env.example`. Use a private local SQLite path and `http://localhost:3431` as the
public origin. The [backend guide](onesa-ai-robot-backend/README.md) gives the exact
factory startup command without cloud credentials. In another terminal:

```sh
cd onesa-ai-robot-frontend
npm ci --ignore-scripts
npm run build
ROBOT_API_URL=http://127.0.0.1:8431 npm start
```

Open `http://localhost:3431` for product information and `/console` for operator sign-in.
The product is **pre-launch, under development**, with **protected access for
authorized users**. To exercise the new administration software locally, explicitly
set `ROBOT_ADMINISTRATOR_NAME` to the configured `ROBOT_OPERATOR_NAME`; leaving it
empty grants no administrator role. The designated administrator can allow or block
physical-operation permission after password confirmation. The console separately
shows connection, readiness and actual operation: hardware is still being developed,
so allowing permission does not connect a controller or start movement. Permission
belongs to the issuing session and is revoked on logout, expiry, restart or Stop.
It is not stored in the simulation task journal and never replays existing tasks.
The simulator starts stopped. Reset requires operator confirmation and never resumes
an old task. No sibling repository, paid inference, cloud database or physical robot
is required for this local path.

Run backend lint/types/tests and frontend build/types/unit/browser checks using
[Build and Test](docs/engineering/BUILD_AND_TEST.md). Browser tests use an isolated
simulator and synthetic credentials. They cover system-light/dark appearance, live
preference changes, keyboard access and safe operator flows. Appearance follows the
browser/OS; there is no appearance selector, stored override or clock schedule.
Shared Onesa foundations are version-pinned while Robot retains its teal engineering
identity and dedicated operational shell.
Console sign-in performs bounded readiness checks before submitting credentials;
temporary unavailability retains masked entries for an explicit retry. Versioned
Robot SVG/ICO/touch icons preserve approved Onesa artwork and distinct product identity.

The permanent branches are **dev**, **staging** and **main**. Normal contributions
follow **dev → staging → main**, with exact-source CI, hosted staging,
qualification and the current owner-authorized release process. See
[engineering policies](AGENTS.md), [onboarding](docs/engineering/ENGINEERING_ONBOARDING.md)
and [deployment](docs/engineering/DEPLOYMENT.md). GitHub Free conventions do not prove
server-enforced branch protection. The repositories retain independent deployment,
authentication and data boundaries. The existing release workflow supports an explicit,
strictly verified frontend-only release that retains an unchanged qualified backend;
it still requires fresh hosted staging and owner authorization. Temporary Dependabot security PRs and necessary
security release candidates are allowed under the documented security procedure; they
do not authorize automatic merges or production releases. Ordinary version PRs stay disabled.

[Onesa Developer Docs](https://docs.onesa.eu) contains approved public material.
Detailed engineering, release evidence and operational instructions require authorized
internal access; sensitive records and credentials stay outside documentation builds.

Report suspected vulnerabilities privately to [info@onesa.eu](mailto:info@onesa.eu)
or GitHub private vulnerability reporting when available. Provide affected version,
impact and a minimal safe reproduction; do not post sensitive details publicly or send
passwords, customer records or exploit payloads. Support is limited to the latest
reviewed main revision. No historical-support promise, bounty or response SLA is asserted.

Maintained by Onesa UG (haftungsbeschränkt), Heidelberg, Germany. No project license
has been approved; open-weight models or dependency licenses do not make this
repository open-source. Preserve all third-party licenses and notices.
