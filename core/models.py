"""Canonical data models for the DIL digital twin race engineer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrackFeatures:
    """Feature vector (no geometry). Drives grip, drag scaling, and wear."""

    name: str
    grip: float
    tire_deg: float
    drag_factor: float


@dataclass(slots=True)
class CarState:
    """Minimal vehicle + lap progress state."""

    speed: float  # m/s
    position: float  # m along lap
    lap_time: float  # s into current lap
    tire_wear: float  # 0.0 → 1.0
    fuel: float  # fraction 0–1 (% full)


@dataclass(frozen=True, slots=True)
class DriverInput:
    """Normalized driver commands (steering unused in longitudinal-only physics)."""

    throttle: float  # 0 → 1
    brake: float  # 0 → 1
    steering: float  # -1 → 1
