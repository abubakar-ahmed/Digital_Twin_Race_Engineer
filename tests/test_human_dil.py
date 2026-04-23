"""Phase 3: human DIL pipeline (no pygame required for core tests)."""

from __future__ import annotations

import statistics
import unittest

from core.simulation.tracks import BALANCED

from interfaces.input.human_session import run_human_dil_lap, run_human_dil_steps
from interfaces.input.processing import InputProcessor, apply_deadzone, normalize_pedal_axis
from interfaces.input.raw_types import RawInput


class TestProcessing(unittest.TestCase):
    def test_normalize_invert(self) -> None:
        self.assertAlmostEqual(normalize_pedal_axis(-1.0, invert=True), 1.0)
        self.assertAlmostEqual(normalize_pedal_axis(1.0, invert=True), 0.0)
        self.assertAlmostEqual(normalize_pedal_axis(0.0, invert=True), 0.5)

    def test_deadzone_zeroes_small_values(self) -> None:
        self.assertEqual(apply_deadzone(0.02, 0.05), 0.0)

    def test_smoothing_reduces_spike(self) -> None:
        proc = InputProcessor(
            smoothing_window_throttle=5,
            smoothing_window_brake=5,
            smoothing_window_steering=5,
            deadzone=0.0,
            max_dthrottle_per_s=200.0,
            max_dbrake_per_s=200.0,
        )
        outs: list[float] = []
        for raw_t in [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0]:
            r = RawInput(0.0, raw_t, 0.0, pedals_are_axes=False)
            outs.append(proc.process(r, 0.05).throttle)
        self.assertLess(statistics.pstdev(outs[-3:]), 0.25)


class TestHumanDILLoop(unittest.TestCase):
    def test_throttle_responsiveness_speed_increases(self) -> None:
        """Full throttle → speed rises over first steps."""

        def read_raw() -> RawInput:
            return RawInput(0.0, 1.0, 0.0, pedals_are_axes=False)

        proc = InputProcessor(
            smoothing_window_throttle=3,
            smoothing_window_brake=3,
            smoothing_window_steering=3,
            deadzone=0.0,
            max_dthrottle_per_s=200.0,
            max_dbrake_per_s=200.0,
        )
        log = run_human_dil_steps(BALANCED, read_raw, n_steps=120, dt=1 / 60.0, processor=proc)
        self.assertGreater(log[45]["speed"], log[0]["speed"])

    def test_full_lap_completion_and_telemetry_shape(self) -> None:
        """Scripted human can finish lap; rows include steering."""

        def read_raw() -> RawInput:
            return RawInput(0.0, 0.88, 0.02, pedals_are_axes=False)

        log = run_human_dil_lap(
            BALANCED,
            read_raw,
            dt=0.05,
            max_steps=600_000,
            print_smoothness=False,
            print_live_delta=False,
        )
        self.assertGreaterEqual(log[-1]["position"], 5000.0 - 1.0)
        for key in (
            "time",
            "speed",
            "position",
            "tire_wear",
            "throttle",
            "brake",
            "steering",
            "wall_time",
            "proc_throttle",
            "raw_throttle_axis",
        ):
            self.assertIn(key, log[0])

    def test_repeatability_deterministic_script(self) -> None:
        """Same scripted input → same lap time."""

        def read_raw() -> RawInput:
            return RawInput(0.05, 0.85, 0.0, pedals_are_axes=False)

        a = run_human_dil_lap(BALANCED, read_raw, dt=0.05, print_smoothness=False, print_live_delta=False)[-1][
            "time"
        ]
        b = run_human_dil_lap(BALANCED, read_raw, dt=0.05, print_smoothness=False, print_live_delta=False)[-1][
            "time"
        ]
        self.assertEqual(a, b)

    def test_smooth_throttle_command_vs_raw_spikes(self) -> None:
        """Smoothed pipeline → lower variance in commanded throttle (logged) vs window=1."""
        t = 0

        def noisy() -> RawInput:
            nonlocal t
            t += 1
            spike = 1.0 if t % 3 == 0 else 0.4
            return RawInput(0.0, spike, 0.0, pedals_are_axes=False)

        smooth_proc = InputProcessor(
            smoothing_window_throttle=7,
            smoothing_window_brake=7,
            smoothing_window_steering=7,
            deadzone=0.0,
            max_dthrottle_per_s=200.0,
            max_dbrake_per_s=200.0,
        )
        log_smooth = run_human_dil_steps(BALANCED, noisy, n_steps=400, dt=0.05, processor=smooth_proc)
        th_s = [r["throttle"] for r in log_smooth[50:200]]
        raw_proc = InputProcessor(
            smoothing_window_throttle=1,
            smoothing_window_brake=1,
            smoothing_window_steering=1,
            deadzone=0.0,
            max_dthrottle_per_s=200.0,
            max_dbrake_per_s=200.0,
        )
        t = 0
        log_raw = run_human_dil_steps(BALANCED, noisy, n_steps=400, dt=0.05, processor=raw_proc)
        th_r = [r["throttle"] for r in log_raw[50:200]]
        self.assertLess(statistics.pstdev(th_s), statistics.pstdev(th_r))


if __name__ == "__main__":
    unittest.main()
