"""Reviewed backend layouts; production native Python needs verified remote storage."""

NATIVE_BUILD = "python -m pip install --require-hashes -r requirements.lock"
NATIVE_START = "sh start.sh"


def kind(service):
    details = service.get("serviceDetails", {})
    for value in (service.get("runtime"), details.get("runtime")):
        if value is not None:
            return value
    return details.get("env") or service.get("env")


def layout(service):
    runtime = kind(service)
    if runtime == "docker":
        return {
            "dockerfilePath": "./Dockerfile",
            "dockerContext": ".",
            "dockerCommand": "",
        }
    if runtime == "python":
        return {"buildCommand": NATIVE_BUILD, "startCommand": NATIVE_START}
    return None


def verified(service):
    expected = layout(service)
    actual = service.get("serviceDetails", {}).get("envSpecificDetails", {})
    return expected is not None and all(
        actual.get(key, "") == value for key, value in expected.items()
    )


def allowed(service, environment, *, durable_remote=False):
    return verified(service) and (
        kind(service) == "docker"
        or (
            kind(service) == "python"
            and (
                environment == "Staging"
                or (environment == "Production" and durable_remote)
            )
        )
    )
