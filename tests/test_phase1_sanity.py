"""Phase 1 sanity checks from the build spec."""

from __future__ import annotations

import unittest

from core.models import CarState, DriverInput
from core.simulation import (
    BALANCED,
    HIGH_DOWNFORCE,
    POWER_TRACK,
    initial_car_state,
    run_lap,
    update_physics,
)
from core.simulation.physics import PhysicsParams
from core.simulation.tracks import TRACKS


class TestPhase1Sanity(unittest.TestCase):
    def test_full_throttle_speed_increases(self) -> None:
        """Full throttle → speed increases smoothly (early phase before drag limit)."""
        track = BALANCED
        s = initial_car_state()
        dt = 0.05
        p = PhysicsParams()
        prev = s.speed
        for _ in range(25):
            update_physics(s, DriverInput(1.0, 0.0, 0.0), track, dt, params=p)
            self.assertGreaterEqual(s.speed, prev - 1e-9)
            prev = s.speed
        self.assertGreater(s.speed, 1.0)

    def test_brake_reduces_speed(self) -> None:
        """Brake → speed drops."""
        track = BALANCED
        s = CarState(speed=40.0, position=0.0, lap_time=0.0, tire_wear=0.1, fuel=1.0)
        dt = 0.05
        before = s.speed
        update_physics(s, DriverInput(0.0, 1.0, 0.0), track, dt)
        self.assertLess(s.speed, before)

    def test_long_run_tire_wear_increases(self) -> None:
        """Long run → tire wear increases."""
        track = BALANCED

        def push(_: CarState) -> DriverInput:
            return DriverInput(0.9, 0.0, 0.0)

        log = run_lap(track, push, dt=0.05)
        self.assertGreater(log[-1]["tire_wear"], log[0]["tire_wear"])

    def test_tracks_differ(self) -> None:
        """Different tracks behave differently (steady cruise before lap end)."""
        dt = 0.05

        def cruise(_: CarState) -> DriverInput:
            return DriverInput(0.85, 0.0, 0.0)

        t_high = run_lap(HIGH_DOWNFORCE, cruise, dt=dt)
        t_pow = run_lap(POWER_TRACK, cruise, dt=dt)
        # Power track: lower drag → higher terminal speed by end of straight phase
        self.assertNotAlmostEqual(t_high[-1]["speed"], t_pow[-1]["speed"], places=2)
        # High tire_deg track should accumulate more wear for same inputs
        self.assertGreater(t_high[-1]["tire_wear"], t_pow[-1]["tire_wear"])


class TestTracksRegistry(unittest.TestCase):
    def test_three_named_tracks(self) -> None:
        self.assertEqual(set(TRACKS.keys()), {"high_downforce", "power_track", "balanced"})


if __name__ == "__main__":
    unittest.main()
