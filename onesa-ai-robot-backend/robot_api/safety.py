"""Independent deterministic gate. Model output cannot grant execution permission."""

import time
from math import isfinite
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: UUID
    issued_at: float
    target_radians: float = Field(ge=-1, le=1)
    duration_seconds: float = Field(ge=1, le=10)


class SafetyViolation(ValueError):
    pass


class SafetyGate:
    """Bounds for a synthetic joint, not approved limits for any physical robot."""

    position_limit = 1.0
    velocity_limit = 0.4
    acceleration_limit = 0.6
    freshness_seconds = 15.0

    def validate(self, command: Proposal, start: float, instant: float | None = None) -> None:
        clock = time.time() if instant is None else instant
        age = clock - command.issued_at
        if not isfinite(age) or age < -1 or age > self.freshness_seconds:
            raise SafetyViolation("Stale or future proposal")
        distance = abs(command.target_radians - start)
        # Exact peak derivatives of the quintic smooth-step trajectory.
        self.check(
            start,
            1.875 * distance / command.duration_seconds,
            5.774 * distance / command.duration_seconds**2,
        )
        self.check(command.target_radians, 0, 0)

    def check(self, position: float, velocity: float, acceleration: float) -> None:
        if not all(isfinite(v) for v in (position, velocity, acceleration)):
            raise SafetyViolation("Nonfinite state")
        if (
            abs(position) > self.position_limit
            or abs(velocity) > self.velocity_limit
            or abs(acceleration) > self.acceleration_limit
        ):
            raise SafetyViolation("Synthetic joint safety limit exceeded")

    def sample(
        self, start: float, target: float, duration: float, elapsed: float
    ) -> tuple[float, float, float]:
        t = min(1.0, max(0.0, elapsed / duration))
        delta = target - start
        position = start + delta * (10 * t**3 - 15 * t**4 + 6 * t**5)
        velocity = delta * (30 * t**2 - 60 * t**3 + 30 * t**4) / duration
        acceleration = delta * (60 * t - 180 * t**2 + 120 * t**3) / duration**2
        self.check(position, velocity, acceleration)
        return position, velocity, acceleration
