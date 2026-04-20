"""Simulation loop: driver input → physics → telemetry rows."""

from __future__ import annotations

from collections.abc import Callable, Iterator

from core.models import CarState, DriverInput, TrackFeatures

from core.simulation.constants import TRACK_LENGTH
from core.simulation.physics import PhysicsParams, update_physics


def initial_car_state(
    *,
    speed: float = 0.0,
    position: float = 0.0,
    lap_time: float = 0.0,
    tire_wear: float = 0.0,
    fuel: float = 1.0,
) -> CarState:
    return CarState(
        speed=speed,
        position=position,
        lap_time=lap_time,
        tire_wear=tire_wear,
        fuel=fuel,
    )


def telemetry_row(state: CarState, inp: DriverInput) -> dict[str, float]:
    """One log record per spec (JSON-serializable values)."""
    return {
        "time": state.lap_time,
        "speed": state.speed,
        "tire_wear": state.tire_wear,
        "position": state.position,
        "throttle": inp.throttle,
        "brake": inp.brake,
    }


def run_lap(
    track: TrackFeatures,
    get_driver_input: Callable[[CarState], DriverInput],
    *,
    dt: float = 0.05,
    max_steps: int = 500_000,
    params: PhysicsParams | None = None,
    state: CarState | None = None,
) -> list[dict[str, float]]:
    """
    Until position reaches TRACK_LENGTH: read input, update physics, append telemetry.
    """
    s = state or initial_car_state()
    log: list[dict[str, float]] = []
    p = params or PhysicsParams()
    steps = 0
    while s.position < TRACK_LENGTH and steps < max_steps:
        inp = get_driver_input(s)
        update_physics(s, inp, track, dt, params=p)
        log.append(telemetry_row(s, inp))
        steps += 1
    if s.position < TRACK_LENGTH:
        raise RuntimeError("Lap did not complete: increase throttle or max_steps")
    return log


def simulate_stream(
    track: TrackFeatures,
    get_driver_input: Callable[[int, CarState], DriverInput],
    *,
    dt: float = 0.05,
    max_steps: int = 200_000,
    params: PhysicsParams | None = None,
    state: CarState | None = None,
) -> Iterator[dict[str, float]]:
    """Same physics as run_lap but yields rows until one lap completes or max_steps."""
    s = state or initial_car_state()
    p = params or PhysicsParams()
    for tick in range(max_steps):
        if s.position >= TRACK_LENGTH:
            break
        inp = get_driver_input(tick, s)
        update_physics(s, inp, track, dt, params=p)
        yield telemetry_row(s, inp)
