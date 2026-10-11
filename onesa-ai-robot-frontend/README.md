# Robot operator interface

The existing Onesa branding and static HTML/CSS interface now connect to an
independent authenticated software simulator through a fixed same-origin proxy.
No browser storage retains passwords, session tokens or control keys.

```sh
npm ci --ignore-scripts
npm run build
npm run typecheck
npm test
ROBOT_API_URL=http://127.0.0.1:8431 npm start
```

Use Node 24. PORT defaults to 3431. `ROBOT_API_URL` is server-only and must be a
credential-free HTTP(S) origin. Remote gateways require TLS. The proxy forwards only
the Robot session cookie and needed Origin/CSRF/content headers; provider bypass
headers/cookies are not forwarded. Backend `ROBOT_PUBLIC_ORIGIN` must match the
browser origin exactly. The interface is a software simulation, never live telemetry.

`npm run test:e2e` requires an isolated simulator, synthetic operator
`browser-test-operator-only`, and matching installed Chromium/Firefox/WebKit binaries.
The suite checks five viewport widths, keyboard entry, login/reset/proposal/approval/
completion/stop/logout and automated WCAG rules. Manual accessibility acceptance
remains separate. Do not use a real operator password or live hardware for tests.

`docker build -t onesa-robot-interface:local .` builds a separate non-root Node image.
The Vercel adapter reuses the same proxy boundary, but an actual Vercel build and
protected staged deployment still need qualification. `git.deploymentEnabled=false`
prevents automatic Git deployment; no public release is implied by a branch push.
API schema/types are generated from the backend, checked with
`python scripts/check-contracts.py` from the repository root using the backend venv.

Hosted staging and owner-approved release instructions are in the
[cloud release guide](../docs/engineering/AUTOMATED_QUALIFICATION.md). Configure a
server-only `ROBOT_API_URL` per Vercel environment. The monorepo CLI runs from repository
root and project root remains `onesa-ai-robot-frontend`. `npm run lint` checks source
syntax; build/types/unit, cross-browser flows and accessibility remain independent gates.
