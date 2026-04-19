"""Canonical data models for the DIL digital twin race engineer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrackFeatures:
    """Static or slowly-varying track characterization used by twin and optimization."""

    grip: float
    tire_deg: float
    avg_speed: float
    corner_density: float
    straight_ratio: float


@dataclass(frozen=True, slots=True)
class CarState:
    """Vehicle state at a sample instant (telemetry / simulation tick)."""

    speed: float
    tire_wear: float
    fuel: float
    lap_time: float


@dataclass(frozen=True, slots=True)
class DriverInput:
    """Normalized driver commands for a control step."""

    steering: float
    throttle: float
    brake: float
