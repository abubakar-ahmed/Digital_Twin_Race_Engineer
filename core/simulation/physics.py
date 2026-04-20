"""Controllable longitudinal update: next_state = f(state, input, track)."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import CarState, DriverInput, TrackFeatures

from core.simulation.constants import MAX_SPEED


@dataclass(frozen=True, slots=True)
class PhysicsParams:
    """Coefficients for acc = throttle*A*grip - brake*B - C*drag_factor*v^2 - D*tire_wear."""

    A: float = 6.5
    B: float = 11.0
    C: float = 0.018
    D: float = 2.8
    wear_scale: float = 8e-5
    fuel_per_throttle: float = 0.00035
    grip_failure_factor: float = 0.15


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def effective_grip(track: TrackFeatures, tire_wear: float, params: PhysicsParams) -> float:
    """Grip from track, with a sharp loss when the tire is nearly gone."""
    g = track.grip
    if tire_wear > 0.95:
        g *= params.grip_failure_factor
    return max(g, 0.05)


def acceleration_m_s2(
    speed: float,
    inp: DriverInput,
    track: TrackFeatures,
    tire_wear: float,
    params: PhysicsParams,
) -> float:
    """
    acc = (throttle * A) * grip - (brake * B) - (C * drag_factor * v^2) - (tire_wear * D)
    Drag uses track.drag_factor; grip boosts throttle term; worn tires pull acceleration down.
    """
    t = _clamp01(inp.throttle)
    b = _clamp01(inp.brake)
    tw = min(1.0, max(0.0, tire_wear))
    g = effective_grip(track, tw, params)
    drag = params.C * track.drag_factor * speed * abs(speed)
    return t * params.A * g - b * params.B - drag - tw * params.D


def update_physics(
    state: CarState,
    inp: DriverInput,
    track: TrackFeatures,
    dt: float,
    *,
    params: PhysicsParams | None = None,
) -> CarState:
    """Single integration step; updates speed, position, lap time, tire wear, fuel."""
    if dt <= 0.0:
        raise ValueError("dt must be positive")
    p = params or PhysicsParams()
    acc = acceleration_m_s2(state.speed, inp, track, state.tire_wear, p)
    new_speed = state.speed + acc * dt
    if new_speed < 0.0:
        new_speed = 0.0
    if new_speed > MAX_SPEED:
        new_speed = MAX_SPEED

    t = _clamp01(inp.throttle)
    b = _clamp01(inp.brake)
    wear_rate = track.tire_deg * (t + b) * p.wear_scale
    new_wear = state.tire_wear + wear_rate * dt
    if new_wear > 1.0:
        new_wear = 1.0

    new_fuel = state.fuel - p.fuel_per_throttle * t * dt
    if new_fuel < 0.0:
        new_fuel = 0.0

    new_position = state.position + new_speed * dt
    new_lap_time = state.lap_time + dt

    state.speed = new_speed
    state.position = new_position
    state.lap_time = new_lap_time
    state.tire_wear = new_wear
    state.fuel = new_fuel
    return state
