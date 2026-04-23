"""Calibration JSON, slew, smoothness score."""

from __future__ import annotations

import tempfile
import unittest

from interfaces.input.calibration import (
    CalibrationProfile,
    build_profile_from_samples,
    load_calibration,
    save_calibration,
)
from interfaces.input.processing import InputProcessor
from interfaces.input.raw_types import RawInput

from core.twin.smoothness import driver_smoothness_score_percent


class TestCalibration(unittest.TestCase):
    def test_roundtrip_json(self) -> None:
        n = [RawInput(0.05, 0.2, 0.2, True)]
        t = [RawInput(0.0, -0.9, 0.2, True)]
        b = [RawInput(0.0, 0.2, 0.85, True)]
        sl = [RawInput(-0.95, 0.2, 0.2, True)]
        sr = [RawInput(0.92, 0.2, 0.2, True)]
        p = build_profile_from_samples(n, t, b, sl, sr)
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/cal.json"
            save_calibration(path, p)
            q = load_calibration(path)
        self.assertAlmostEqual(p.steering_min, q.steering_min, places=4)

    def test_apply_maps_pedals(self) -> None:
        p = CalibrationProfile(
            steering_min=-1.0,
            steering_max=1.0,
            steering_center=0.0,
            throttle_axis_neutral=0.0,
            throttle_axis_full=-1.0,
            brake_axis_neutral=0.0,
            brake_axis_full=1.0,
        )
        r = p.apply(RawInput(0.0, -1.0, 1.0, True))
        self.assertAlmostEqual(r.throttle, 1.0, places=3)
        self.assertAlmostEqual(r.brake, 1.0, places=3)


class TestSlew(unittest.TestCase):
    def test_slew_limits_spike(self) -> None:
        proc = InputProcessor(
            smoothing_window_throttle=1,
            smoothing_window_brake=1,
            smoothing_window_steering=1,
            max_dthrottle_per_s=2.0,
            max_dbrake_per_s=10.0,
            default_dt=0.05,
        )
        proc.reset()
        proc.process(RawInput(0.0, 0.0, 0.0, False), 0.05)
        t1 = proc.process(RawInput(0.0, 1.0, 0.0, False), 0.05).throttle
        t2 = proc.process(RawInput(0.0, 1.0, 0.0, False), 0.05).throttle
        self.assertLessEqual(t1, 0.11)
        self.assertGreaterEqual(t2, t1)


class TestSmoothness(unittest.TestCase):
    def test_score_bounds(self) -> None:
        tel = [{"throttle": 0.5, "brake": 0.0, "steering": 0.0} for _ in range(20)]
        s = driver_smoothness_score_percent(tel)
        self.assertGreater(s, 90.0)


if __name__ == "__main__":
    unittest.main()
