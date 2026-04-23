"""Run virtual driver laps, record benchmark time + telemetry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from core.models import CarState, DriverInput, TrackFeatures

from core.simulation.lap_simulator import initial_car_state, run_lap
from core.simulation.physics import PhysicsParams


@dataclass(slots=True)
class OptimalLapResult:
    track_name: str
    driver_id: str
    lap_time_s: float
    telemetry: list[dict[str, float]]
    lap_times_s: tuple[float, ...]


def lap_time_from_trace(rows: list[dict[str, float]]) -> float:
    """Elapsed time for the lap (last sample's clock)."""
    if not rows:
        return 0.0
    return float(rows[-1]["time"])


def run_virtual_lap(
    track: TrackFeatures,
    driver: Callable[[CarState], DriverInput],
    *,
    driver_id: str = "virtual",
    dt: float = 0.05,
    params: PhysicsParams | None = None,
    reset_state: bool = True,
    state: CarState | None = None,
) -> OptimalLapResult:
    """
    One full lap from standstill (or provided state). Resets PID if driver has reset().
    """
    if hasattr(driver, "reset"):
        driver.reset()  # type: ignore[attr-defined]
    s = initial_car_state() if reset_state and state is None else (state or initial_car_state())

    def get_input(st: CarState) -> DriverInput:
        return driver(st)

    rows = run_lap(track, get_input, dt=dt, params=params, state=s)
    t = lap_time_from_trace(rows)
    return OptimalLapResult(
        track_name=track.name,
        driver_id=driver_id,
        lap_time_s=t,
        telemetry=rows,
        lap_times_s=(t,),
    )


def run_virtual_laps(
    track: TrackFeatures,
    driver: Callable[[CarState], DriverInput],
    *,
    n_laps: int,
    driver_id: str = "virtual",
    dt: float = 0.05,
    params: PhysicsParams | None = None,
    carry_tire_wear: bool = True,
) -> OptimalLapResult:
    """Several laps in sequence; optional tire wear carry-over between laps."""
    if n_laps < 1:
        raise ValueError("n_laps must be >= 1")
    if hasattr(driver, "reset"):
        driver.reset()  # type: ignore[attr-defined]
    s = initial_car_state()
    times: list[float] = []
    best_rows: list[dict[str, float]] = []
    best_t = float("inf")

    for _ in range(n_laps):
        s.position = 0.0
        s.lap_time = 0.0
        if not carry_tire_wear:
            s.tire_wear = 0.0

        def get_input(st: CarState) -> DriverInput:
            return driver(st)

        rows = run_lap(track, get_input, dt=dt, params=params, state=s)
        lt = lap_time_from_trace(rows)
        times.append(lt)
        if lt < best_t:
            best_t = lt
            best_rows = list(rows)

    return OptimalLapResult(
        track_name=track.name,
        driver_id=driver_id,
        lap_time_s=min(times),
        telemetry=best_rows,
        lap_times_s=tuple(times),
    )


def benchmark_payload(result: OptimalLapResult) -> dict[str, Any]:
    """JSON-serializable benchmark + trace."""
    return {
        "track_name": result.track_name,
        "driver_id": result.driver_id,
        "optimal_lap_time_s": result.lap_time_s,
        "lap_times_s": list(result.lap_times_s),
        "telemetry": result.telemetry,
    }


def save_benchmark(path: str | Path, result: OptimalLapResult, *, indent: int = 2) -> None:
    """Write optimal lap time + full telemetry trace."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(benchmark_payload(result), f, indent=indent)
