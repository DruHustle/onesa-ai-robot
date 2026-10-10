# Build and test readiness

Frontend: `onesa-ai-robot-frontend/public/` contains a dependency-free static preview.
Serve it using the frontend README instructions; there is no compilation step.
Desktop/mobile rendering and overflow were checked locally at 1440px and 390px.
Backend: `onesa-ai-robot-backend/` has documentation/configuration examples only.
Both application builds/tests are **not applicable: not implemented**. Do not report
this repository as an operational robot or independently deployable implementation.

CI runs `publication-hygiene` and `scaffold-check` for the documentation boundary only.
Before application readiness, add per-application reproducible installs, lint/type
checks, unit tests, Docker builds, service health checks and contract integration
against a mock AI-platform API. Each Docker build must use only that app's directory.
Add hardware tests only through an approved controlled runner with actuation disabled
by default. Required application status checks must be added after implementation.
