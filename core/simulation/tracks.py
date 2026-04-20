"""Three feature-only tracks."""

from __future__ import annotations

from core.models import TrackFeatures

HIGH_DOWNFORCE = TrackFeatures(
    name="high_downforce",
    grip=1.18,
    tire_deg=0.42,
    drag_factor=1.12,
)

POWER_TRACK = TrackFeatures(
    name="power_track",
    grip=0.95,
    tire_deg=0.22,
    drag_factor=0.72,
)

BALANCED = TrackFeatures(
    name="balanced",
    grip=1.05,
    tire_deg=0.32,
    drag_factor=0.95,
)

TRACKS: dict[str, TrackFeatures] = {
    "high_downforce": HIGH_DOWNFORCE,
    "power_track": POWER_TRACK,
    "balanced": BALANCED,
}
