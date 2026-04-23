"""Virtual segments from lap progress (no geometry)."""

from __future__ import annotations

from enum import Enum

from core.models import TrackFeatures

from core.simulation.constants import MAX_SPEED, TRACK_LENGTH


class VirtualSegment(Enum):
    STRAIGHT = "straight"
    MEDIUM_CORNER = "medium_corner"
    MIXED = "mixed"


def lap_fraction(position: float) -> float:
    """0–1 progress along the lap (feature-based, not geometric)."""
    if TRACK_LENGTH <= 0:
        return 0.0
    return max(0.0, min(1.0, position / TRACK_LENGTH))


def segment_from_fraction(t: float) -> VirtualSegment:
    """Piecewise segments: 0–30% straight, 30–60% corner, 60–100% mixed."""
    if t < 0.30:
        return VirtualSegment.STRAIGHT
    if t < 0.60:
        return VirtualSegment.MEDIUM_CORNER
    return VirtualSegment.MIXED


def target_speed_m_s(
    track: TrackFeatures,
    position: float,
    tire_wear: float,
) -> float:
    """
    Reference speed (setpoint) from segment, grip, drag, and tire wear.
    Stays below MAX_SPEED and remains deterministic.
    """
    t = lap_fraction(position)
    seg = segment_from_fraction(t)
    wear = max(0.0, min(1.0, tire_wear))
    wear_factor = 1.0 - 0.28 * wear

    g = max(0.5, track.grip)
    drag = track.drag_factor

    if seg is VirtualSegment.STRAIGHT:
        # High speed; extra drag pulls top end down slightly
        base = 0.90 * MAX_SPEED * wear_factor
        base *= 1.0 - 0.06 * max(0.0, drag - 0.85)
    elif seg is VirtualSegment.MEDIUM_CORNER:
        base = MAX_SPEED * 0.52 * (0.92 + 0.08 * g) * wear_factor
    else:
        base = MAX_SPEED * 0.68 * (0.88 + 0.10 * g) * wear_factor
        base *= 1.0 - 0.03 * max(0.0, drag - 0.90)

    return max(6.0, min(MAX_SPEED * 0.97, base))
