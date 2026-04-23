"""Phase 2: virtual drivers, optimal lap benchmark, PID vs rule vs naive."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.models import DriverInput
from core.driver import (
    PIDVirtualDriver,
    RuleBasedDriver,
    benchmark_payload,
    run_virtual_lap,
    run_virtual_laps,
    save_benchmark,
)
from core.simulation.tracks import BALANCED, POWER_TRACK, TRACKS


def _naive_driver(throttle: float = 0.78):
    def _drive(_state):
        return DriverInput(throttle, 0.0, 0.0)

    return _drive


class TestRuleAndPID(unittest.TestCase):
    def test_pid_beats_naive_on_all_tracks(self) -> None:
        """PID reference should be materially faster than flat throttle."""
        for _name, tr in TRACKS.items():
            pid = PIDVirtualDriver(tr)
            t_pid = run_virtual_lap(tr, pid, driver_id="pid").lap_time_s
            t_naive = run_virtual_lap(tr, _naive_driver(), driver_id="naive").lap_time_s
            self.assertLess(t_pid, t_naive - 5.0, msg=_name)

    def test_pid_matches_or_beats_rule_within_dt(self) -> None:
        """PID should be within one sim step of rule-based (same dt)."""
        dt = 0.05
        for _name, tr in TRACKS.items():
            rule = RuleBasedDriver(tr)
            pid = PIDVirtualDriver(tr)
            t_rule = run_virtual_lap(tr, rule, dt=dt).lap_time_s
            t_pid = run_virtual_lap(tr, pid, dt=dt).lap_time_s
            self.assertLessEqual(t_pid, t_rule + dt + 1e-6, msg=_name)

    def test_deterministic_repeat(self) -> None:
        """Same driver + track → same lap time."""
        pid = PIDVirtualDriver(BALANCED)
        a = run_virtual_lap(BALANCED, pid).lap_time_s
        b = run_virtual_lap(BALANCED, pid).lap_time_s
        self.assertEqual(a, b)

    def test_multi_lap_returns_min_time_and_trace(self) -> None:
        pid = PIDVirtualDriver(POWER_TRACK)
        out = run_virtual_laps(POWER_TRACK, pid, n_laps=2, driver_id="pid", carry_tire_wear=True)
        self.assertEqual(len(out.lap_times_s), 2)
        self.assertGreater(out.telemetry[-1]["time"], 0.0)


class TestBenchmarkJson(unittest.TestCase):
    def test_save_benchmark_roundtrip(self) -> None:
        pid = PIDVirtualDriver(BALANCED)
        res = run_virtual_lap(BALANCED, pid, driver_id="pid_optimal")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bench.json"
            save_benchmark(path, res)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("optimal_lap_time_s", data)
        self.assertIn("telemetry", data)
        self.assertEqual(data["optimal_lap_time_s"], res.lap_time_s)
        self.assertEqual(len(data["telemetry"]), len(res.telemetry))
        payload = benchmark_payload(res)
        self.assertEqual(payload["driver_id"], res.driver_id)


if __name__ == "__main__":
    unittest.main()
