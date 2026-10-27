# Robot simulator deployment and recovery

<!-- onesa-protected-source: robot-deployment -->

Detailed operational instructions are maintained in protected Engineering Docs.
This public source is a reference page, not a deployment or recovery runbook.

[Open the protected guide](https://docs.engineering.onesa.eu/docs/ecosystem/ROBOT_DEPLOYMENT).
Sign in through Onesa Portal with an individually approved engineering identity.

Public repository history may contain earlier editions; moving this active copy
does not erase historical exposure. Credentials, records and release evidence
belong in their existing restricted stores, never in this reference page.

## Oracle owner-run evidence bridge

The new `scripts/release/oracle_owner.py` adapter preserves owner-run receipts
with workflow run ID `0` and genuine CI run references. It requires a separately
commissioned, pinned external verifier and owner-controlled signing custody.
Repository code or an unsigned JSON file supplies no release authority.
The protected guide contains installation, qualification and recovery instructions;
source implementation alone does not establish commissioning or deployment.

The Robot-specific extension adds an immutable installer, API and frontend runners,
existing-operator credential confirmation, and synthetic hosted probes to that same
bridge. Its source is `scripts/release/oracle_install.py`, `oracle_robot.py`,
`oracle_robot_frontend.py` and `oracle_robot_probe.py`. It does not create a service
or grant authority to repository jobs. Three-engine tooling is disposable and remains
independent of the application images. Installation, commissioning, qualification
and verified production acceptance must each be recorded separately in the protected
guide; the presence of these modules does not establish any of those outcomes.
