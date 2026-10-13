"""Outbound TLS telemetry demonstrator. No command receiver or actuator adapter."""

import json
import os
import time
import urllib.error
import urllib.request

url = os.environ["ROBOT_EDGE_CLOUD_URL"]
from urllib.parse import urlsplit

parsed = urlsplit(url)
if (
    parsed.scheme != "https"
    or not parsed.hostname
    or parsed.username
    or parsed.password
    or parsed.path not in {"", "/"}
    or parsed.query
    or parsed.fragment
):
    raise SystemExit("Expected credential-free HTTPS cloud origin")
token = os.environ["ROBOT_EDGE_TOKEN"]
device = os.environ["ROBOT_EDGE_DEVICE_ID"]
if not device.startswith("synthetic-") or len(token) < 64:
    raise SystemExit("Configure a synthetic device and independent strong token")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = urllib.request.build_opener(NoRedirect())


def request(path, body=None):
    req = urllib.request.Request(
        url.rstrip("/") + path,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        data=json.dumps(body).encode() if body is not None else None,
    )
    with opener.open(req, timeout=5) as response:
        return json.loads(response.read(16384))


# New process obtains a fresh boot binding; never replay queued messages after failure.
challenge = request("/api/v1/edge/challenge")
sequence = challenge["next_sequence"]
while True:
    try:
        request(
            "/api/v1/edge/telemetry",
            {
                "version": 1,
                "device_id": device,
                "boot_challenge": challenge["boot_challenge"],
                "sequence": sequence,
                "observed_at": time.time(),
                "mode": "simulation",
                "physical_actuation": False,
                "stopped": True,
                "position_radians": 0.0,
            },
        )
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        # Fail closed; an operator restarts after inspecting the connection.
        raise SystemExit(
            "Telemetry connection lost; agent stopped without command replay"
        ) from None
    sequence += 1
    time.sleep(1)
