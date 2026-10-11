"""Authenticated synthetic simulator acceptance. No hardware or real user data."""

import argparse
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from cloud import NoRedirect, origin
from evidence import Rejected, require, save

CHECKS = [
    "backend_readiness",
    "frontend_availability",
    "authentication",
    "authorization",
    "simulation",
    "safety_denial",
    "cancellation",
    "connection_loss",
    "stale_command",
    "replay_rejection",
    "audit_history",
    "storage_isolation",
    "edge_telemetry",
]


class Simulator:
    def __init__(self, url):
        self.url = origin(url)
        self.csrf = ""
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar)
        )

    def call(self, route, body=None, expected=200, csrf=True):
        headers = {"Origin": self.url, "Content-Type": "application/json"}
        if self.csrf and csrf:
            headers["X-CSRF-Token"] = self.csrf
        bypass = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET")
        if bypass:
            headers["x-vercel-protection-bypass"] = bypass
        request = urllib.request.Request(
            self.url + route,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            response = self.opener.open(request, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            require(response.code == expected, "Unexpected simulator HTTP status")
            raw = response.read(1024 * 1024)
            if response.headers.get_content_type() == "application/json":
                return json.loads(raw)
            return raw


def run(url, environment):
    record = {
        "scope": "software-simulation-only",
        "status": "BLOCKED",
        "checks": {name: "BLOCKED" for name in CHECKS},
        "physical_hardware_approved": False,
    }
    password = os.environ.get("ROBOT_TEST_PASSWORD", "")
    name = os.environ.get("ROBOT_TEST_OPERATOR", "")
    if (
        not password
        or not name
        or os.environ.get("ROBOT_TEST_SCOPE")
        != "approved-synthetic-" + environment.lower()
    ):
        return record
    if environment == "Staging":
        origin(url, ".vercel.app")
    else:
        require(
            origin(url) == origin(os.environ.get("ROBOT_PUBLIC_ORIGIN", "")),
            "Unapproved production operator origin",
        )
    api = Simulator(url)
    logged_in = False
    checks = record["checks"]
    try:
        require(b"Software simulation" in api.call("/"), "Unexpected frontend")
        checks["frontend_availability"] = "PASS"
        ready = api.call("/api/v1/ready")
        require(
            ready.get("mode") == "simulation"
            and ready.get("physical_actuation") is False
            and ready.get("deployment_environment") == environment.lower(),
            "Unsafe runtime",
        )
        checks["backend_readiness"] = "PASS"
        require(
            ready.get("storage_mode")
            == (os.environ.get("ROBOT_STORAGE_MODE", "ephemeral-simulation")
                if environment == "Staging" else "persistent"),
            "Storage scope mismatch",
        )
        checks["storage_isolation"] = "PASS"
        api.call("/api/v1/status", expected=401)
        api.call(
            "/api/v1/auth/login",
            {"name": name, "password": "invalid-synthetic-login"},
            expected=401,
        )
        login = api.call("/api/v1/auth/login", {"name": name, "password": password})
        api.csrf = login["csrf"]
        logged_in = True
        require(
            any(cookie.secure and cookie.name == "robot_session" for cookie in api.jar),
            "Secure cookie required",
        )
        checks["authentication"] = "PASS"
        api.call("/api/v1/stop", {}, expected=403, csrf=False)
        checks["authorization"] = "PASS"
        # Independent outbound device identity is telemetry-only; it cannot approve tasks.
        edge_token = os.environ.get("ROBOT_EDGE_TOKEN", "")
        edge_device = os.environ.get("ROBOT_EDGE_DEVICE_ID", "")
        require(
            len(edge_token) >= 64 and edge_device.startswith("synthetic-"),
            "Synthetic edge identity required",
        )
        backend = origin(os.environ["ROBOT_API_URL"], ".onrender.com")
        opener = urllib.request.build_opener(NoRedirect())

        def edge_call(route, body=None):
            request = urllib.request.Request(
                backend + route,
                headers={
                    "Authorization": "Bearer " + edge_token,
                    "Content-Type": "application/json",
                },
                data=json.dumps(body).encode() if body is not None else None,
            )
            with opener.open(request, timeout=10) as response:
                require(response.code == 200, "Edge telemetry HTTP failure")
                return json.loads(response.read(16384))

        challenge = edge_call("/api/v1/edge/challenge")
        edge_call(
            "/api/v1/edge/telemetry",
            {
                "version": 1,
                "device_id": edge_device,
                "boot_challenge": challenge["boot_challenge"],
                "sequence": challenge["next_sequence"],
                "observed_at": time.time(),
                "mode": "simulation",
                "physical_actuation": False,
                "stopped": True,
                "position_radians": 0.0,
            },
        )
        require(
            api.call("/api/v1/status")["capabilities"]["edge_telemetry"]
            == "simulation_connected",
            "Missing edge telemetry",
        )
        time.sleep(4)
        require(
            api.call("/api/v1/status")["capabilities"]["edge_telemetry"]
            == "not_connected",
            "Stale edge appears connected",
        )
        checks["edge_telemetry"] = "PASS"
        api.call("/api/v1/stop", {})

        def reset():
            api.call("/api/v1/reset", {"password": password})

        def proposal(**changes):
            return {
                "command_id": str(uuid4()),
                "issued_at": time.time(),
                "target_radians": 0.1,
                "duration_seconds": 2,
                **changes,
            }

        def create(value):
            api.call("/api/v1/tasks", value, expected=201)
            return value["command_id"]

        def approve(identifier):
            api.call("/api/v1/tasks/" + identifier + "/approve", {"password": password})

        reset()
        api.call("/api/v1/tasks", proposal(issued_at=time.time() - 60), expected=422)
        checks["stale_command"] = "PASS"
        api.call(
            "/api/v1/tasks",
            proposal(target_radians=0.9, duration_seconds=1),
            expected=422,
        )
        checks["safety_denial"] = "PASS"
        value = proposal()
        identifier = create(value)
        api.call("/api/v1/tasks", value, expected=409)
        approve(identifier)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            api.call("/api/v1/heartbeat", {})
            history = api.call("/api/v1/tasks")["tasks"]
            if any(
                task["id"] == identifier and task["state"] == "completed"
                for task in history
            ):
                break
            time.sleep(0.25)
        else:
            raise Rejected("Simulation did not complete")
        checks["simulation"] = "PASS"
        api.call(
            "/api/v1/tasks/" + identifier + "/approve",
            {"password": password},
            expected=409,
        )
        checks["replay_rejection"] = "PASS"
        cancelled = create(proposal(target_radians=0.15, duration_seconds=10))
        approve(cancelled)
        api.call("/api/v1/tasks/" + cancelled + "/cancel", {})
        require(api.call("/api/v1/status")["stopped"], "Cancellation must latch stop")
        checks["cancellation"] = "PASS"
        reset()
        # Revoke the approving session: execution cannot survive reconnect/login.
        disconnected = create(proposal(target_radians=0.2, duration_seconds=10))
        approve(disconnected)
        api.call("/api/v1/auth/logout", {})
        logged_in = False
        api.csrf = api.call("/api/v1/auth/login", {"name": name, "password": password})[
            "csrf"
        ]
        logged_in = True
        require(api.call("/api/v1/status")["stopped"], "Lost authority did not stop")
        history = api.call("/api/v1/tasks")["tasks"]
        require(
            any(
                task["id"] == disconnected
                and task["state"] == "cancelled"
                and task["reason"] == "session_revoked"
                for task in history
            ),
            "Missing cancellation audit",
        )
        checks["connection_loss"] = "PASS"
        require(
            any(
                task["id"] == identifier and task["state"] == "completed"
                for task in history
            )
            and any(
                task["id"] == cancelled and task["state"] == "cancelled"
                for task in history
            ),
            "Missing task audit",
        )
        checks["audit_history"] = "PASS"
        record["status"] = "PASS"
    except (Rejected, ValueError, KeyError, urllib.error.URLError, TimeoutError):
        record["status"] = "FAIL"
    finally:
        if logged_in:
            try:
                api.call("/api/v1/stop", {})
                api.call("/api/v1/auth/logout", {})
            except (Rejected, ValueError, urllib.error.URLError, TimeoutError):
                record["status"] = "FAIL"
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=["Staging", "Production"])
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    directory = Path(args.directory)
    operator_file = directory / (
        "operator-url.txt" if args.environment == "Production" else "frontend-url.txt"
    )
    result = run(operator_file.read_text().strip(), args.environment)
    save(result, directory / "smoke.json")
    require(
        result["status"] == "PASS", "Hosted simulation acceptance blocked or failed"
    )
