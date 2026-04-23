"""PID speed controller: setpoint = target speed, PV = current speed → throttle/brake."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.models import CarState, DriverInput, TrackFeatures

from core.driver.segments import target_speed_m_s
from core.simulation.constants import MAX_SPEED

if TYPE_CHECKING:
    from core.optimization.speed_envelope import SpeedEnvelope


@dataclass(slots=True)
class PIDGains:
    kp: float = 0.105
    ki: float = 0.0020
    kd: float = 0.014


@dataclass(slots=True)
class PIDVirtualDriver:
    """
    Setpoint tracking: feedforward from target speed + PID on speed error.
    Optional SpeedEnvelope replaces hand-tuned segment targets.
    aggression ∈ [0,1] scales setpoint / feedforward (conservative → aggressive).
    """

    track: TrackFeatures
    dt: float = 0.05
    gains: PIDGains = field(default_factory=PIDGains)
    accel_scale: float = 4.1
    feedforward_gain: float = 0.945
    envelope: SpeedEnvelope | None = None
    aggression: float = 0.88

    _integral: float = field(init=False, default=0.0)
    _prev_error: float = field(init=False, default=0.0)

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0

    def _setpoint(self, state: CarState) -> float:
        agg = min(1.0, max(0.0, self.aggression))
        if self.envelope is not None:
            return self.envelope.target_speed(state.position, state.tire_wear, agg, self.track)
        sp = target_speed_m_s(self.track, state.position, state.tire_wear)
        return sp * (0.86 + 0.14 * agg)

    def _effective_feedforward_gain(self) -> float:
        agg = min(1.0, max(0.0, self.aggression))
        return self.feedforward_gain * (0.88 + 0.12 * agg)

    def __call__(self, state: CarState) -> DriverInput:
        sp = self._setpoint(state)
        pv = state.speed
        e = sp - pv
        if self.dt <= 0.0:
            dedt = 0.0
        else:
            dedt = (e - self._prev_error) / self.dt
        self._prev_error = e

        g = self.gains
        u_pid = g.kp * e + g.ki * self._integral + g.kd * dedt

        self._integral += e * self.dt
        self._integral = max(-22.0, min(22.0, self._integral))

        ff = min(1.0, (sp / MAX_SPEED) * self._effective_feedforward_gain())
        intent = ff + u_pid / self.accel_scale

        if intent >= 0.0:
            throttle = min(1.0, intent)
            brake = 0.0
        else:
            throttle = 0.0
            brake = min(1.0, -intent)

        return DriverInput(throttle, brake, 0.0)
