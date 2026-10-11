# Independent software builds and tests

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

Scope: software simulation only. ROS 2 interface package compilation/messaging,
model endpoints, actual sensor/actuator behavior, emergency-stop hardware and real
edge-network latency remain NOT TESTED or BLOCKED until their targets exist.
Automated accessibility checks do not certify complete WCAG 2.2 AA compliance.
