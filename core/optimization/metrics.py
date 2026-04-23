"""Benchmark metrics: sectors, consistency, efficiency."""

from __future__ import annotations

import statistics
from typing import Any

from core.driver.optimal_lap import OptimalLapResult
from core.simulation.constants import TRACK_LENGTH


def sector_times_s(telemetry: list[dict[str, float]], *, lap_length: float = TRACK_LENGTH) -> dict[str, float]:
    """
    Virtual sectors aligned with driver segments: 0–30%, 30–60%, 60–100% of lap length.
    Returns split times in seconds (sum ≈ lap time if position is monotone).
    """
    if not telemetry:
        return {"sector_1_s": 0.0, "sector_2_s": 0.0, "sector_3_s": 0.0}
    b1 = 0.30 * lap_length
    b2 = 0.60 * lap_length

    def first_time_at(min_pos: float) -> float:
        for row in telemetry:
            if row["position"] >= min_pos:
                return float(row["time"])
        return float(telemetry[-1]["time"])

    t0 = float(telemetry[0]["time"])
    t1 = first_time_at(b1)
    t2 = first_time_at(b2)
    t_end = float(telemetry[-1]["time"])
    return {
        "sector_1_s": max(0.0, t1 - t0),
        "sector_2_s": max(0.0, t2 - t1),
        "sector_3_s": max(0.0, t_end - t2),
    }


def lap_time_variance_s2(lap_times_s: list[float]) -> float:
    """Sample variance of lap times (0 if fewer than 2 samples)."""
    if len(lap_times_s) < 2:
        return 0.0
    return float(statistics.pvariance(lap_times_s))


def efficiency_ratio(human_lap_s: float, optimal_lap_s: float) -> float:
    """>1 means human slower than optimal reference."""
    if optimal_lap_s <= 0.0:
        return float("inf")
    return human_lap_s / optimal_lap_s


def enriched_benchmark_payload(
    result: OptimalLapResult,
    *,
    human_lap_s: float | None = None,
) -> dict[str, Any]:
    """Lap trace + sector splits + consistency + optional human efficiency."""
    sectors = sector_times_s(result.telemetry)
    variance = lap_time_variance_s2(list(result.lap_times_s))
    out: dict[str, Any] = {
        "track_name": result.track_name,
        "driver_id": result.driver_id,
        "optimal_lap_time_s": result.lap_time_s,
        "lap_times_s": list(result.lap_times_s),
        "lap_time_variance_s2": variance,
        "sectors_s": sectors,
        "telemetry": result.telemetry,
    }
    if human_lap_s is not None:
        out["human_lap_s"] = human_lap_s
        out["efficiency_ratio_human_over_optimal"] = efficiency_ratio(human_lap_s, result.lap_time_s)
    return out
