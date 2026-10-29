"""A real owned process crash must not replay a pending/running inspection."""

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

from robot_api.security import password_hash


def test_abrupt_process_restart_revokes_session_and_preserves_partial_run(tmp_path, monkeypatch):
    # Owned loopback fixtures must never send synthetic operator credentials to
    # inherited workstation proxies, including unsupported SOCKS transports.
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "socks5h://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    password = secrets.token_urlsafe(24)
    operator = "fixture-" + uuid4().hex[:12]
    backend = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        env = {
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(backend),
            "PYTHONDONTWRITEBYTECODE": "1",
            "ROBOT_PUBLIC_ORIGIN": origin,
            "ROBOT_OPERATOR_NAME": operator,
            "ROBOT_OPERATOR_PASSWORD_HASH": password_hash(password),
            "ROBOT_DATABASE_PATH": str(tmp_path / "crash.sqlite3"),
            "ROBOT_ACTUATION_ENABLED": "false",
        }
        process = None
        with (tmp_path / "process.log").open("wb") as log:

            def start():
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "robot_api.main:create_app",
                        "--factory",
                        "--fd",
                        str(listener.fileno()),
                        "--no-access-log",
                        "--no-proxy-headers",
                    ],
                    cwd=backend,
                    env=env,
                    pass_fds=(listener.fileno(),),
                    stdout=log,
                    stderr=log,
                )
                try:
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        assert child.poll() is None, "Owned fixture process exited before readiness"
                        try:
                            if (
                                httpx.get(
                                    origin + "/api/v1/ready", timeout=0.3, trust_env=False
                                ).status_code
                                == 200
                            ):
                                return child
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.05)
                    raise AssertionError("Owned fixture readiness deadline exceeded")
                except BaseException:
                    if child.poll() is None:
                        child.terminate()
                        child.wait(timeout=5)
                    raise

            try:
                process = start()
                with httpx.Client(
                    base_url=origin, headers={"Origin": origin}, timeout=3, trust_env=False
                ) as api:

                    def login():
                        response = api.post(
                            "/api/v1/auth/login", json={"name": operator, "password": password}
                        )
                        assert response.status_code == 200
                        api.headers["X-CSRF-Token"] = response.json()["csrf"]

                    login()
                    assert api.post("/api/v1/reset", json={"password": password}).status_code == 200
                    detail = api.post(
                        "/api/v1/missions",
                        json={
                            "command_id": str(uuid4()),
                            "robot_profile_id": "sim-inspector",
                            "scenario": "normal",
                        },
                    ).json()
                    path = f"/api/v1/missions/{detail['id']}"
                    assert (
                        api.post(
                            path + "/approve",
                            json={
                                "password": password,
                                "expected_plan_sha256": detail["record"]["plan_sha256"],
                            },
                        ).status_code
                        == 200
                    )
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        api.post("/api/v1/heartbeat", json={})
                        partial = api.get(path).json()
                        if partial["record"]["observations"]:
                            break
                        time.sleep(0.1)
                    assert partial["record"]["outcome"] == "running"
                    assert len(partial["record"]["observations"]) == 3
                    # Only our direct child, disposable data and no external credentials.
                    process.kill()
                    process.wait(timeout=5)
                    process = start()
                    assert api.get(path).status_code == 401
                    login()
                    restored = api.get(path).json()
                    assert restored["record"]["plan_sha256"] == partial["record"]["plan_sha256"]
                    assert restored["record"]["observations"] == partial["record"]["observations"]
                    assert restored["record"]["outcome"] == "interrupted"
                    assert restored["record"]["events"][-1]["detail"] == "process_restart"
                    state = api.get("/api/v1/status").json()
                    assert state["stopped"] and state["active_task"] is None
                    assert (
                        api.post(
                            path + "/approve",
                            json={
                                "password": password,
                                "expected_plan_sha256": detail["record"]["plan_sha256"],
                            },
                        ).status_code
                        == 409
                    )
            finally:
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
