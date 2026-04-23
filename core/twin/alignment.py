"""Align human vs optimal traces on a common distance grid."""

from __future__ import annotations

from bisect import bisect_right

Row = dict[str, float]


def _trace_has_key(trace: list[Row], key: str) -> bool:
    return bool(trace) and key in trace[0]


def sort_by_position(rows: list[Row]) -> list[Row]:
    return sorted(rows, key=lambda r: float(r["position"]))


def interpolate_channel(trace: list[Row], position: float, key: str) -> float:
    """Linear interpolation of `key` vs position; trace sorted by position."""
    if not trace:
        return 0.0
    if position <= float(trace[0]["position"]):
        return float(trace[0][key])
    if position >= float(trace[-1]["position"]):
        return float(trace[-1][key])
    pos = [float(r["position"]) for r in trace]
    i = bisect_right(pos, position) - 1
    i = max(0, min(i, len(trace) - 2))
    p0, p1 = float(trace[i]["position"]), float(trace[i + 1]["position"])
    if p1 <= p0 + 1e-9:
        return float(trace[i][key])
    t = (position - p0) / (p1 - p0)
    v0, v1 = float(trace[i][key]), float(trace[i + 1][key])
    return v0 + t * (v1 - v0)


def position_grid(lap_length: float, step_m: float) -> list[float]:
    if step_m <= 0:
        raise ValueError("step_m must be positive")
    pts: list[float] = [0.0]
    x = step_m
    while x < lap_length - 1e-9:
        pts.append(x)
        x += step_m
    if abs(pts[-1] - lap_length) > 1e-6:
        pts.append(lap_length)
    return pts


def align_traces(
    human: list[Row],
    optimal: list[Row],
    *,
    lap_length: float,
    step_m: float = 50.0,
) -> list[dict[str, float]]:
    """
    Interpolate both laps onto the same distance samples.
    Each row: position, human_time, optimal_time, human_speed, optimal_speed,
    human_tire_wear, optimal_tire_wear, delta_t, delta_v (optimal - human speed).
    """
    h = sort_by_position(human)
    o = sort_by_position(optimal)
    grid = position_grid(lap_length, step_m)
    out: list[dict[str, float]] = []
    for p in grid:
        ht = interpolate_channel(h, p, "time")
        ot = interpolate_channel(o, p, "time")
        hs = interpolate_channel(h, p, "speed")
        os_ = interpolate_channel(o, p, "speed")
        htw = interpolate_channel(h, p, "tire_wear")
        otw = interpolate_channel(o, p, "tire_wear")
        row: dict[str, float] = {
            "position": p,
            "human_time": ht,
            "optimal_time": ot,
            "human_speed": hs,
            "optimal_speed": os_,
            "human_tire_wear": htw,
            "optimal_tire_wear": otw,
            "delta_t": ht - ot,
            "delta_v": os_ - hs,
        }
        if _trace_has_key(h, "steering") and _trace_has_key(o, "steering"):
            hst = interpolate_channel(h, p, "steering")
            ost = interpolate_channel(o, p, "steering")
            row["human_steering"] = hst
            row["optimal_steering"] = ost
            row["delta_steering"] = ost - hst
        if _trace_has_key(h, "throttle") and _trace_has_key(o, "throttle"):
            htp = interpolate_channel(h, p, "throttle")
            otp = interpolate_channel(o, p, "throttle")
            row["human_throttle"] = htp
            row["optimal_throttle"] = otp
            row["delta_throttle"] = otp - htp
        if _trace_has_key(h, "brake") and _trace_has_key(o, "brake"):
            row["human_brake"] = interpolate_channel(h, p, "brake")
            row["optimal_brake"] = interpolate_channel(o, p, "brake")
        out.append(row)
    return out
