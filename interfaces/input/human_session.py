"""Human-in-the-loop: read device → process → physics → telemetry @ fixed rate."""

from __future__ import annotations

import time
from collections.abc import Callable

from core.models import CarState, DriverInput, TrackFeatures

from core.simulation.constants import TRACK_LENGTH
from core.simulation.lap_simulator import initial_car_state, telemetry_row
from core.simulation.physics import PhysicsParams, update_physics

from interfaces.input.processing import InputProcessor
from interfaces.input.raw_types import RawInput


def human_telemetry_row(
    state: CarState,
    inp: DriverInput,
    proc_debug: dict[str, float],
    wall_time: float,
) -> dict[str, float]:
    """Simulation row + wall clock + raw vs processed controls (Phase 4 / delta)."""
    row = telemetry_row(state, inp)
    row["wall_time"] = wall_time
    row.update(proc_debug)
    return row


def run_human_dil_lap(
    track: TrackFeatures,
    read_raw: Callable[[], RawInput],
    *,
    dt: float = 1.0 / 60.0,
    processor: InputProcessor | None = None,
    params: PhysicsParams | None = None,
    state: CarState | None = None,
    max_steps: int = 600_000,
    use_pygame_clock: bool = False,
    warn_loop_ms: float = 20.0,
    optimal_reference: list[dict[str, float]] | None = None,
    live_delta_interval: int = 25,
    print_live_delta: bool = True,
    print_smoothness: bool = True,
) -> list[dict[str, float]]:
    """
    Core DIL loop: raw input → normalize/smooth/slew → physics → rich telemetry.

    If ``optimal_reference`` is set, prints a ~2 Hz live Δt line vs that trace.
    """
    proc = processor or InputProcessor()
    proc.reset()
    s = state or initial_car_state()
    p = params or PhysicsParams()
    log: list[dict[str, float]] = []
    clock = None
    if use_pygame_clock:
        import pygame

        clock = pygame.time.Clock()
        tick_hz = max(1, int(round(1.0 / dt)))

    steps = 0
    while s.position < TRACK_LENGTH and steps < max_steps:
        t0 = time.perf_counter()
        raw = read_raw()
        inp = proc.process(raw, dt)
        update_physics(s, inp, track, dt, params=p)
        wall = time.time()
        log.append(human_telemetry_row(s, inp, proc.last_debug, wall))
        if clock is not None:
            clock.tick(tick_hz)

        if (
            optimal_reference
            and live_delta_interval > 0
            and steps > 0
            and steps % live_delta_interval == 0
            and print_live_delta
        ):
            from core.twin.live_delta import format_live_delta_line, top_sector_hint_from_partial

            line = format_live_delta_line(log, optimal_reference)
            if line:
                print(line)
            hint = top_sector_hint_from_partial(log, optimal_reference, lap_length=TRACK_LENGTH)
            if hint:
                print(hint)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if elapsed_ms > warn_loop_ms and steps % 120 == 0:
            print(f"[DIL] Warning: loop step {elapsed_ms:.1f} ms (target < {warn_loop_ms:.0f} ms)")
        steps += 1

    if s.position < TRACK_LENGTH:
        raise RuntimeError("Lap did not complete before max_steps")

    if print_smoothness and log:
        from core.twin.smoothness import driver_smoothness_score_percent

        sc = driver_smoothness_score_percent(log)
        print(f"[DIL] Smoothness: {sc:.0f}%")
    return log


def run_human_dil_steps(
    track: TrackFeatures,
    read_raw: Callable[[], RawInput],
    *,
    n_steps: int,
    dt: float = 1.0 / 60.0,
    processor: InputProcessor | None = None,
    params: PhysicsParams | None = None,
    state: CarState | None = None,
    use_pygame_clock: bool = False,
) -> list[dict[str, float]]:
    """Fixed number of physics steps (tests / partial sessions)."""
    if n_steps < 1:
        raise ValueError("n_steps must be >= 1")
    proc = processor or InputProcessor()
    proc.reset()
    s = state or initial_car_state()
    p = params or PhysicsParams()
    log: list[dict[str, float]] = []
    clock = None
    if use_pygame_clock:
        import pygame

        clock = pygame.time.Clock()
        tick_hz = max(1, int(round(1.0 / dt)))
    for _ in range(n_steps):
        raw = read_raw()
        inp = proc.process(raw, dt)
        update_physics(s, inp, track, dt, params=p)
        log.append(human_telemetry_row(s, inp, proc.last_debug, time.time()))
        if clock is not None:
            clock.tick(tick_hz)
    return log


def run_human_dil_lap_pygame(
    track: TrackFeatures,
    *,
    prefer_joystick: bool = True,
    dt: float = 1.0 / 60.0,
    processor: InputProcessor | None = None,
    params: PhysicsParams | None = None,
    optimal_reference: list[dict[str, float]] | None = None,
    live_delta_interval: int = 25,
    print_live_delta: bool = True,
    print_smoothness: bool = True,
) -> list[dict[str, float]]:
    """
    Convenience: pygame backend + fixed-rate clock.
    For headless servers set ``SDL_VIDEODRIVER=dummy`` before import when using keyboard fallback.
    """
    from interfaces.input.pygame_backend import create_pygame_backend

    backend = create_pygame_backend(prefer_joystick=prefer_joystick)

    def read_raw() -> RawInput:
        return backend.read_raw()

    return run_human_dil_lap(
        track,
        read_raw,
        dt=dt,
        processor=processor,
        params=params,
        use_pygame_clock=True,
        optimal_reference=optimal_reference,
        live_delta_interval=live_delta_interval,
        print_live_delta=print_live_delta,
        print_smoothness=print_smoothness,
    )
