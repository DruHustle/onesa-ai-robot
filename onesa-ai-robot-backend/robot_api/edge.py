"""Read-only simulated edge telemetry. This boundary cannot authorize motion."""

import secrets
import time
from collections import deque
from hashlib import sha256
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    device_id: str = Field(pattern=r"^synthetic-[a-z0-9-]{1,48}$")
    boot_challenge: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")
    sequence: int = Field(ge=0)
    observed_at: float
    mode: Literal["simulation"]
    physical_actuation: Literal[False]
    stopped: Literal[True]
    position_radians: float = Field(ge=-1, le=1, allow_inf_nan=False)


class EdgeMonitor:
    def __init__(self, device_id: str, token_sha256: str):
        self.device_id = device_id
        self.token_sha256 = token_sha256
        self.challenge = secrets.token_urlsafe(32)
        self.sequence = -1
        self.observed = 0.0
        self.requests: deque[float] = deque()
        self.audit: deque[dict[str, str | int | float]] = deque(maxlen=100)

    def authorize(self, authorization: str):
        if not self.device_id or not self.token_sha256:
            raise HTTPException(503, "Edge telemetry is not configured")
        if not authorization.startswith("Bearer ") or not secrets.compare_digest(
            sha256(authorization[7:].encode()).hexdigest(), self.token_sha256
        ):
            raise HTTPException(401, "Device authentication required")
        now = time.monotonic()
        while self.requests and self.requests[0] < now - 1:
            self.requests.popleft()
        if len(self.requests) >= 10:
            raise HTTPException(429, "Device rate limit exceeded")
        self.requests.append(now)

    def receive(self, value: Telemetry):
        age = time.time() - value.observed_at
        if value.device_id != self.device_id or not secrets.compare_digest(
            value.boot_challenge, self.challenge
        ):
            raise HTTPException(403, "Device/boot identity mismatch")
        if not 0 <= age <= 3 or value.sequence <= self.sequence:
            raise HTTPException(409, "Stale or replayed telemetry")
        self.sequence = value.sequence
        self.observed = time.monotonic()
        self.audit.append(
            {
                "device_id": self.device_id,
                "sequence": self.sequence,
                "event": "simulation_telemetry",
                "at": time.time(),
            }
        )

    def status(self):
        return (
            "simulation_connected"
            if self.observed and time.monotonic() - self.observed <= 3
            else "not_connected"
        )
