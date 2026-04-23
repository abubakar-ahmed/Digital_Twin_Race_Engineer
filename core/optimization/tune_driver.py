"""Grid search over driver parameters; pick minimum lap time."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from core.models import TrackFeatures

from core.driver.optimal_lap import OptimalLapResult, run_virtual_lap
from core.driver.pid_driver import PIDGains, PIDVirtualDriver
from core.optimization.speed_envelope import SpeedEnvelope

from core.simulation.physics import PhysicsParams


@dataclass(slots=True)
class OptimizedDriverResult:
    best_lap_time_s: float
    best_params: dict[str, float]
    result: OptimalLapResult
    all_trials: list[tuple[dict[str, float], float]]


def optimize_virtual_driver(
    track: TrackFeatures,
    envelope: SpeedEnvelope,
    *,
    physics: PhysicsParams | None = None,
    dt: float = 0.05,
    aggression_grid: tuple[float, ...] = (0.84, 0.90, 0.96),
    kp_scale_grid: tuple[float, ...] = (0.96, 1.04, 1.10),
    feedforward_grid: tuple[float, ...] = (0.935, 0.955),
    accel_scale_grid: tuple[float, ...] = (3.9, 4.3),
    base_gains: PIDGains | None = None,
) -> OptimizedDriverResult:
    """
    Multi-run parameter search: min lap time wins.
    PID tracks the precomputed envelope setpoint curve.
    """
    base = base_gains or PIDGains()
    trials: list[tuple[dict[str, float], float]] = []
    best_t = float("inf")
    best_params: dict[str, float] = {}
    best_result: OptimalLapResult | None = None

    for agg, ks, ff, asc in product(
        aggression_grid,
        kp_scale_grid,
        feedforward_grid,
        accel_scale_grid,
    ):
        gains = PIDGains(
            kp=base.kp * ks,
            ki=base.ki * min(1.15, max(0.85, ks)),
            kd=base.kd * min(1.1, max(0.9, ks)),
        )
        driver = PIDVirtualDriver(
            track,
            dt=dt,
            gains=gains,
            accel_scale=asc,
            feedforward_gain=ff,
            envelope=envelope,
            aggression=agg,
        )
        res = run_virtual_lap(track, driver, driver_id="pid_optimized", dt=dt, params=physics)
        params = {
            "aggression": agg,
            "kp_scale": ks,
            "feedforward_gain": ff,
            "accel_scale": asc,
            "kp": gains.kp,
            "ki": gains.ki,
            "kd": gains.kd,
        }
        trials.append((params, res.lap_time_s))
        if res.lap_time_s < best_t:
            best_t = res.lap_time_s
            best_params = params
            best_result = res

    assert best_result is not None
    return OptimizedDriverResult(
        best_lap_time_s=best_t,
        best_params=best_params,
        result=best_result,
        all_trials=trials,
    )
