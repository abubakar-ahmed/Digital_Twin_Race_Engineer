"""Hardware calibration: capture ranges once, persist to JSON, remap every run."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from interfaces.input.raw_types import RawInput


@dataclass(slots=True)
class CalibrationProfile:
    """Remaps raw wheel axes to logical ranges (saved to JSON)."""

    version: int = 1
    steering_min: float = -1.0
    steering_max: float = 1.0
    steering_center: float = 0.0
    throttle_axis_neutral: float = 0.0
    throttle_axis_full: float = -1.0
    brake_axis_neutral: float = 0.0
    brake_axis_full: float = 1.0

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_json_dict(d: dict[str, Any]) -> CalibrationProfile:
        return CalibrationProfile(
            version=int(d.get("version", 1)),
            steering_min=float(d["steering_min"]),
            steering_max=float(d["steering_max"]),
            steering_center=float(d["steering_center"]),
            throttle_axis_neutral=float(d["throttle_axis_neutral"]),
            throttle_axis_full=float(d["throttle_axis_full"]),
            brake_axis_neutral=float(d["brake_axis_neutral"]),
            brake_axis_full=float(d["brake_axis_full"]),
        )

    def apply(self, raw: RawInput) -> RawInput:
        """Map hardware to logical steering [-1,1] and pedals [0,1] (always pedals_are_axes=False after)."""
        st = _map_linear(raw.steering_axis, self.steering_min, self.steering_max, -1.0, 1.0)
        if not raw.pedals_are_axes:
            return RawInput(steering_axis=st, throttle=raw.throttle, brake=raw.brake, pedals_are_axes=False)
        th01 = _map_axis_to_unit(raw.throttle, self.throttle_axis_neutral, self.throttle_axis_full)
        br01 = _map_axis_to_unit(raw.brake, self.brake_axis_neutral, self.brake_axis_full)
        return RawInput(steering_axis=st, throttle=th01, brake=br01, pedals_are_axes=False)


def _map_linear(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if abs(x1 - x0) < 1e-6:
        return (y0 + y1) * 0.5
    t = (x - x0) / (x1 - x0)
    t = max(0.0, min(1.0, t))
    return y0 + t * (y1 - y0)


def _map_axis_to_unit(axis: float, neutral: float, full: float) -> float:
    """Map pedal axis so neutral→0, full→1 (clamped)."""
    span = full - neutral
    if abs(span) < 1e-6:
        return 0.0
    v = (axis - neutral) / span
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _mean(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    return float(sum(xs) / len(xs))


def build_profile_from_samples(
    neutral: Sequence[RawInput],
    full_throttle: Sequence[RawInput],
    full_brake: Sequence[RawInput],
    steer_left: Sequence[RawInput],
    steer_right: Sequence[RawInput],
) -> CalibrationProfile:
    """Aggregate captured samples into a profile."""
    st_n = [_mean([r.steering_axis for r in neutral])]
    th_n = [_mean([r.throttle for r in neutral])]
    br_n = [_mean([r.brake for r in neutral])]
    th_f = [_mean([r.throttle for r in full_throttle])] if full_throttle else th_n
    br_f = [_mean([r.brake for r in full_brake])] if full_brake else br_n
    sl = [r.steering_axis for r in steer_left] if steer_left else [-1.0]
    sr = [r.steering_axis for r in steer_right] if steer_right else [1.0]
    return CalibrationProfile(
        steering_min=min(sl),
        steering_max=max(sr),
        steering_center=st_n[0],
        throttle_axis_neutral=th_n[0],
        throttle_axis_full=th_f[0],
        brake_axis_neutral=br_n[0],
        brake_axis_full=br_f[0],
    )


def save_calibration(path: str | Path, profile: CalibrationProfile) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(profile.to_json_dict(), f, indent=2)


def load_calibration(path: str | Path) -> CalibrationProfile:
    with Path(path).open(encoding="utf-8") as f:
        d = json.load(f)
    return CalibrationProfile.from_json_dict(d)


def run_interactive_calibration(
    read_raw: Callable[[], RawInput],
    *,
    phase_duration_s: float = 2.0,
    print_fn: Callable[[str], None] = print,
) -> CalibrationProfile:
    """
    ~10 s routine: neutral → full throttle → full brake → steer left → steer right.
    Call ``read_raw()`` at game rate from your pygame loop (this function busy-waits per phase).
    """
    buckets: dict[str, list[RawInput]] = defaultdict(list)
    phases: list[tuple[str, str]] = [
        ("Neutral: release pedals, hands off wheel", "neutral"),
        ("Full throttle: press accelerator fully", "full_throttle"),
        ("Full brake: press brake fully", "full_brake"),
        ("Turn wheel fully left and hold", "steer_left"),
        ("Turn wheel fully right and hold", "steer_right"),
    ]
    for instruction, key in phases:
        print_fn(f"[CAL] {instruction} ({phase_duration_s:.0f}s)…")
        t_end = time.monotonic() + phase_duration_s
        while time.monotonic() < t_end:
            buckets[key].append(read_raw())
            time.sleep(0.016)
    return build_profile_from_samples(
        buckets["neutral"],
        buckets["full_throttle"],
        buckets["full_brake"],
        buckets["steer_left"],
        buckets["steer_right"],
    )
