"""Deterministic bang–coast driver from target speed (baseline for PID)."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import CarState, DriverInput, TrackFeatures

from core.driver.segments import target_speed_m_s
from core.simulation.constants import MAX_SPEED


@dataclass(slots=True)
class RuleBasedDriver:
    """
    Simple control: full throttle below target, small brake above.
    aggression ∈ [0,1]: higher → tighter deadband, stronger braking.
    """

    track: TrackFeatures
    brake_gain: float = 0.18
    deadband_m_s: float = 0.35
    aggression: float = 0.88

    def __call__(self, state: CarState) -> DriverInput:
        agg = min(1.0, max(0.0, self.aggression))
        sp = target_speed_m_s(self.track, state.position, state.tire_wear) * (0.86 + 0.14 * agg)
        sp = max(6.0, min(sp, MAX_SPEED * 0.99))
        dead = self.deadband_m_s * (1.35 - 0.35 * agg)
        brake = min(1.0, self.brake_gain * (0.82 + 0.18 * agg))
        err = sp - state.speed
        if err > dead:
            return DriverInput(1.0, 0.0, 0.0)
        if err < -dead:
            return DriverInput(0.0, brake, 0.0)
        return DriverInput(0.0, 0.0, 0.0)
