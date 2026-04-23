"""Precomputed speed vs lap fraction from short-horizon rollouts (no ML)."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

from core.models import CarState, DriverInput, TrackFeatures

from core.driver.segments import lap_fraction
from core.simulation.constants import MAX_SPEED, TRACK_LENGTH
from core.simulation.physics import PhysicsParams, update_physics


def _moving_average(values: list[float], window: int) -> list[float]:
    if window < 1 or not values:
        return list(values)
    w = min(window, len(values))
    if w % 2 == 0:
        w -= 1
    if w < 1:
        return list(values)
    half = w // 2
    out: list[float] = []
    n = len(values)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def _horizon_score(
    track: TrackFeatures,
    pos0: float,
    v_target: float,
    *,
    horizon_steps: int,
    dt: float,
    physics: PhysicsParams,
    tire_penalty: float = 420.0,
) -> float:
    """Simulate forward from pos0 chasing v_target; reward distance, penalize wear."""
    v0 = min(max(6.0, v_target * 0.52), MAX_SPEED * 0.55)
    s = CarState(speed=v0, position=pos0, lap_time=0.0, tire_wear=0.0, fuel=1.0)
    p0 = s.position
    w0 = s.tire_wear
    for _ in range(horizon_steps):
        if s.speed < v_target - 0.55:
            inp = DriverInput(1.0, 0.0, 0.0)
        elif s.speed > v_target + 0.55:
            inp = DriverInput(0.0, 0.22, 0.0)
        else:
            inp = DriverInput(0.38, 0.0, 0.0)
        update_physics(s, inp, track, dt, params=physics)
    return (s.position - p0) - tire_penalty * (s.tire_wear - w0)


@dataclass(frozen=True, slots=True)
class SpeedEnvelope:
    """
    Lap-fraction → speed table (smooth). Built offline; used as PID setpoint curve.
    """

    track_name: str
    fractions: tuple[float, ...]
    speeds_m_s: tuple[float, ...]

    def target_speed(
        self,
        position: float,
        tire_wear: float,
        aggression: float,
        track: TrackFeatures,
    ) -> float:
        """
        Interpolated envelope × wear × aggression.
        aggression ∈ [0,1]: conservative → push harder (still clamped).
        """
        f = lap_fraction(position)
        v = self._interp(f)
        tw = min(1.0, max(0.0, tire_wear))
        v *= 1.0 - 0.24 * tw
        agg = min(1.0, max(0.0, aggression))
        v *= 0.72 + 0.28 * agg
        # Light track coupling so envelope stays consistent with grip/drag model
        v *= 0.97 + 0.03 * min(track.grip, 1.35) / 1.05
        v *= 1.0 - 0.04 * max(0.0, track.drag_factor - 0.88)
        return max(6.0, min(MAX_SPEED * 0.985, v))

    def _interp(self, f: float) -> float:
        xs = self.fractions
        ys = self.speeds_m_s
        if f <= xs[0]:
            return ys[0]
        if f >= xs[-1]:
            return ys[-1]
        i = bisect_left(xs, f) - 1
        i = max(0, min(i, len(xs) - 2))
        t = (f - xs[i]) / (xs[i + 1] - xs[i]) if xs[i + 1] > xs[i] else 0.0
        return ys[i] + t * (ys[i + 1] - ys[i])


def build_speed_envelope(
    track: TrackFeatures,
    *,
    n_bins: int = 40,
    n_speed_samples: int = 20,
    horizon_s: float = 1.25,
    dt: float = 0.05,
    physics: PhysicsParams | None = None,
    smooth_window: int = 5,
) -> SpeedEnvelope:
    """
    For each lap-fraction bin, try candidate speeds with a short rollout and pick the best.
    Curve is smoothed for DIL-friendly reference tracking.
    """
    if n_bins < 4:
        raise ValueError("n_bins must be at least 4")
    p = physics or PhysicsParams()
    horizon_steps = max(3, int(horizon_s / dt))
    lo_v, hi_v = 7.0, MAX_SPEED * 0.96
    candidates = [lo_v + (hi_v - lo_v) * k / max(1, n_speed_samples - 1) for k in range(n_speed_samples)]

    fractions: list[float] = []
    raw_speeds: list[float] = []

    for i in range(n_bins):
        f_mid = (i + 0.5) / n_bins
        pos0 = min(TRACK_LENGTH * 0.999, f_mid * TRACK_LENGTH)
        best_v = candidates[0]
        best_s = -1e18
        for v_c in candidates:
            sc = _horizon_score(track, pos0, v_c, horizon_steps=horizon_steps, dt=dt, physics=p)
            if sc > best_s:
                best_s = sc
                best_v = v_c
        fractions.append(f_mid)
        raw_speeds.append(best_v)

    smoothed = _moving_average(raw_speeds, smooth_window)
    speeds = tuple(max(6.0, min(MAX_SPEED * 0.985, v)) for v in smoothed)
    fr = tuple(fractions)
    return SpeedEnvelope(track_name=track.name, fractions=fr, speeds_m_s=speeds)
