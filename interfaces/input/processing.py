"""Normalize, deadzone, per-channel smoothing, slew limits; optional calibration."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from core.models import DriverInput

from interfaces.input.calibration import CalibrationProfile
from interfaces.input.raw_types import RawInput


def clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def apply_deadzone(x: float, dz: float) -> float:
    if dz <= 0.0:
        return x
    if abs(x) < dz:
        return 0.0
    sign = 1.0 if x > 0 else -1.0
    mag = abs(x) - dz
    return sign * (mag / (1.0 - dz)) if dz < 1.0 else 0.0


def apply_pedal_deadzone01(x: float, dz: float) -> float:
    """Deadzone for [0,1] pedal (drop tiny resting noise)."""
    if dz <= 0.0:
        return x
    if x < dz:
        return 0.0
    return min(1.0, (x - dz) / (1.0 - dz))


def normalize_pedal_axis(axis: float, *, invert: bool = True) -> float:
    """Map typical wheel pedal axis [-1, 1] → throttle/brake [0, 1]."""
    if invert:
        v = axis * -0.5 + 0.5
    else:
        v = axis * 0.5 + 0.5
    return clamp01(v)


@dataclass(slots=True)
class InputProcessor:
    """
    Optional calibration → deadzone → pedal normalize (axes) → per-channel MA → slew.
    Throttle/brake: shorter windows (responsive); steering: longer (smoother).
    """

    deadzone: float = 0.05
    pedal_deadzone01: float = 0.02
    smoothing_window_throttle: int = 4
    smoothing_window_brake: int = 4
    smoothing_window_steering: int = 7
    invert_throttle_axis: bool = True
    invert_brake_axis: bool = True
    max_dthrottle_per_s: float = 6.0
    max_dbrake_per_s: float = 8.0
    default_dt: float = 1.0 / 60.0
    calibration: CalibrationProfile | None = None

    _s_th: deque[float] = field(init=False)
    _s_br: deque[float] = field(init=False)
    _s_st: deque[float] = field(init=False)
    _prev_th: float | None = field(init=False, default=None)
    _prev_br: float | None = field(init=False, default=None)
    last_debug: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._s_th = deque(maxlen=max(1, self.smoothing_window_throttle))
        self._s_br = deque(maxlen=max(1, self.smoothing_window_brake))
        self._s_st = deque(maxlen=max(1, self.smoothing_window_steering))

    def reset(self) -> None:
        self._s_th.clear()
        self._s_br.clear()
        self._s_st.clear()
        self._prev_th = None
        self._prev_br = None
        self.last_debug.clear()

    def _ma(self, buf: deque[float], x: float) -> float:
        buf.append(x)
        return sum(buf) / len(buf)

    def _slew(self, prev: float | None, target: float, limit_per_s: float, dt: float) -> float:
        if prev is None:
            return target
        lim = max(0.0, limit_per_s) * dt
        d = target - prev
        d = max(-lim, min(lim, d))
        return clamp01(prev + d)

    def process(self, raw: RawInput, dt: float | None = None) -> DriverInput:
        dt = self.default_dt if dt is None else dt
        raw_hw = raw
        if self.calibration is not None:
            raw = self.calibration.apply(raw_hw)

        steer = apply_deadzone(raw.steering_axis, self.deadzone)
        steer = max(-1.0, min(1.0, steer))

        if raw.pedals_are_axes:
            t_axis = apply_deadzone(raw.throttle, self.deadzone)
            b_axis = apply_deadzone(raw.brake, self.deadzone)
            th = normalize_pedal_axis(t_axis, invert=self.invert_throttle_axis)
            br = normalize_pedal_axis(b_axis, invert=self.invert_brake_axis)
        else:
            th = apply_pedal_deadzone01(clamp01(raw.throttle), self.pedal_deadzone01)
            br = apply_pedal_deadzone01(clamp01(raw.brake), self.pedal_deadzone01)

        th = self._ma(self._s_th, th)
        br = self._ma(self._s_br, br)
        steer = self._ma(self._s_st, steer)
        steer = max(-1.0, min(1.0, steer))

        th = self._slew(self._prev_th, th, self.max_dthrottle_per_s, dt)
        br = self._slew(self._prev_br, br, self.max_dbrake_per_s, dt)
        self._prev_th = th
        self._prev_br = br

        self.last_debug = {
            "raw_steering_axis": float(raw_hw.steering_axis),
            "raw_throttle_axis": float(raw_hw.throttle),
            "raw_brake_axis": float(raw_hw.brake),
            "proc_throttle": float(th),
            "proc_brake": float(br),
            "proc_steering": float(steer),
        }
        return DriverInput(throttle=th, brake=br, steering=steer)
