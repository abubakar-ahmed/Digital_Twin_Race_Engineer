"""Lightweight in-session gap vs optimal reference (~2 Hz console hints)."""

from __future__ import annotations

from core.twin.alignment import interpolate_channel, sort_by_position

Row = dict[str, float]


def cumulative_time_gap_at_position(
    human_trace: list[Row],
    optimal_trace: list[Row],
    position: float,
) -> float:
    """human_time(pos) − optimal_time(pos) on aligned distance (positive = human slower)."""
    h = sort_by_position(human_trace)
    o = sort_by_position(optimal_trace)
    ht = interpolate_channel(h, position, "time")
    ot = interpolate_channel(o, position, "time")
    return ht - ot


def format_live_delta_line(
    human_so_far: list[Row],
    optimal_full: list[Row],
    *,
    min_position_m: float = 200.0,
) -> str | None:
    """Single console line for partial lap; None if not enough data."""
    if not human_so_far or not optimal_full:
        return None
    pos = float(human_so_far[-1]["position"])
    if pos < min_position_m:
        return None
    dt = cumulative_time_gap_at_position(human_so_far, optimal_full, pos)
    hint = ""
    if dt > 0.35:
        hint = " — pace below reference"
    elif dt < -0.05:
        hint = " — ahead of reference segment"
    return f"[Live] @{pos:.0f}m Δt={dt:+.2f}s{hint}"


def top_sector_hint_from_partial(
    human_so_far: list[Row],
    optimal_full: list[Row],
    *,
    lap_length: float,
) -> str | None:
    """Cheap hint: which virtual sector currently carries most of the gap."""
    if not human_so_far or not optimal_full:
        return None
    pos = float(human_so_far[-1]["position"])
    frac = pos / lap_length if lap_length > 0 else 0.0
    if frac < 0.28:
        tag = "T1"
    elif frac < 0.58:
        tag = "T2"
    else:
        tag = "T3"
    dt = cumulative_time_gap_at_position(human_so_far, optimal_full, pos)
    if dt <= 0.12:
        return None
    return f"[Live] {tag}: ≈{dt:+.2f}s vs ref @ {pos:.0f}m"
