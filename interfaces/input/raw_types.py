"""Shared raw input container (avoids circular imports with calibration)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RawInput:
    """Raw channels before normalization (wheel axes or keyboard levels)."""

    steering_axis: float
    throttle: float
    brake: float
    pedals_are_axes: bool = True
