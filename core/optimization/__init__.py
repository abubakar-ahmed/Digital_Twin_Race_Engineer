"""Parameter search, speed envelope, and benchmark metrics."""

from core.optimization.metrics import (
    efficiency_ratio,
    enriched_benchmark_payload,
    lap_time_variance_s2,
    sector_times_s,
)
from core.optimization.speed_envelope import SpeedEnvelope, build_speed_envelope
from core.optimization.tune_driver import OptimizedDriverResult, optimize_virtual_driver

__all__ = [
    "OptimizedDriverResult",
    "SpeedEnvelope",
    "build_speed_envelope",
    "efficiency_ratio",
    "enriched_benchmark_payload",
    "lap_time_variance_s2",
    "optimize_virtual_driver",
    "sector_times_s",
]
