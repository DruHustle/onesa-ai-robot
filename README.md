# Onesa AI Robot

Independent Onesa UG robotics repository. The implemented release scope is an
**authenticated software simulator** with an operator interface and separate Python
API. It has no physical actuator driver, robot camera, connected ROS node or live
STT/VLM/TTS/VLA model. Physical actuation is disabled and enabling it rejects startup.

| Application | Runtime | Build/run guide |
| --- | --- | --- |
| `onesa-ai-robot-frontend/` | Static interface + Node 24 same-origin API proxy | [Frontend](onesa-ai-robot-frontend/README.md) |
| `onesa-ai-robot-backend/` | Python 3.11 / FastAPI / private SQLite | [Backend](onesa-ai-robot-backend/README.md) |

Operators sign in, explicitly reset the simulation stop state, propose a synthetic
joint movement, confirm approval, cancel or stop, and review durable task history.
The independent gate checks freshness, position, velocity and acceleration at
proposal/approval and every simulation step. Session revocation, missed heartbeats,
shutdown and restart revoke execution authority; there is no automatic resume.
The limits apply to a synthetic joint and are not physical robot safety certification.

[Build and tests](docs/engineering/BUILD_AND_TEST.md) ·
[Deployment and recovery](docs/engineering/DEPLOYMENT.md) ·
[Architecture](docs/engineering/SIMULATION_ARCHITECTURE.md) ·
[ROS boundary](ros2/README.md).

`robot.onesa.eu` currently serves the earlier static preview. The simulator candidate
is not publicly promoted by a feature push. Vercel Git deployments are disabled in
its configuration; provider/build/test/release gates must be qualified independently.
Secrets, databases, models, uploads and internal release evidence remain outside Git.
No project licensing or physical hardware operation is authorized by this change.
