"""Driver smoothness from control variance (higher = calmer inputs)."""

from __future__ import annotations

import statistics


def driver_smoothness_score_percent(
    telemetry: list[dict[str, float]],
    *,
    sensitivity: float = 28.0,
) -> float:
    """
    Map variance of (throttle + brake + |steering|) to a 0–100% score.
    Lower variance → higher score (teams value consistency).
    """
    if len(telemetry) < 6:
        return 100.0
    combined: list[float] = []
    for r in telemetry:
        st = float(r.get("steering", 0.0))
        combined.append(float(r["throttle"]) + float(r["brake"]) + abs(st))
    try:
        v = statistics.pvariance(combined)
    except statistics.StatisticsError:
        return 100.0
    score = 100.0 / (1.0 + sensitivity * v)
    return max(0.0, min(100.0, score))
