"""Reviewed backend layouts; native Python is permitted only for free staging."""

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


def allowed(service, environment):
    return verified(service) and (
        kind(service) == "docker"
        or (environment == "Staging" and kind(service) == "python")
    )
