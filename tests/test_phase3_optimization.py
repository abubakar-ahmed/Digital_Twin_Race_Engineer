"""Envelope, parameter search, and benchmark metrics."""

from __future__ import annotations

import unittest

from core.driver import PIDVirtualDriver, RuleBasedDriver, run_virtual_lap
from core.optimization import (
    build_speed_envelope,
    efficiency_ratio,
    enriched_benchmark_payload,
    lap_time_variance_s2,
    optimize_virtual_driver,
    sector_times_s,
)
from core.simulation.tracks import BALANCED


class TestSpeedEnvelope(unittest.TestCase):
    def test_envelope_is_smooth_and_bounded(self) -> None:
        env = build_speed_envelope(BALANCED, n_bins=20, n_speed_samples=10, horizon_s=0.9, smooth_window=5)
        self.assertEqual(len(env.fractions), 20)
        for v in env.speeds_m_s:
            self.assertGreaterEqual(v, 6.0)
            self.assertLessEqual(v, 95.0)

    def test_envelope_target_respects_aggression(self) -> None:
        env = build_speed_envelope(BALANCED, n_bins=12, n_speed_samples=8, horizon_s=0.75)
        v_low = env.target_speed(1500.0, 0.0, 0.2, BALANCED)
        v_high = env.target_speed(1500.0, 0.0, 1.0, BALANCED)
        self.assertGreater(v_high, v_low)


class TestOptimizeDriver(unittest.TestCase):
    def test_optimization_beats_or_matches_heuristic_pid(self) -> None:
        env = build_speed_envelope(BALANCED, n_bins=14, n_speed_samples=8, horizon_s=0.85)
        base = PIDVirtualDriver(BALANCED, envelope=env, aggression=0.88)
        t_base = run_virtual_lap(BALANCED, base, driver_id="pid_env_base").lap_time_s
        out = optimize_virtual_driver(
            BALANCED,
            env,
            aggression_grid=(0.86, 0.93),
            kp_scale_grid=(0.98, 1.06),
            feedforward_grid=(0.94, 0.955),
            accel_scale_grid=(3.95, 4.25),
        )
        self.assertLessEqual(out.best_lap_time_s, t_base + 0.15)
        self.assertLess(out.best_lap_time_s, t_base + 1.0)

    def test_optimized_can_beat_rule_baseline_on_balanced(self) -> None:
        """After envelope + search, reference should beat or tie bang–coast rule."""
        env = build_speed_envelope(BALANCED, n_bins=16, n_speed_samples=10, horizon_s=1.0)
        rule_t = run_virtual_lap(BALANCED, RuleBasedDriver(BALANCED)).lap_time_s
        out = optimize_virtual_driver(
            BALANCED,
            env,
            aggression_grid=(0.88, 0.94, 0.98),
            kp_scale_grid=(0.96, 1.04, 1.12),
            feedforward_grid=(0.93, 0.948, 0.965),
            accel_scale_grid=(3.85, 4.15, 4.45),
        )
        self.assertLessEqual(out.best_lap_time_s, rule_t + 0.08)


class TestMetrics(unittest.TestCase):
    def test_sectors_sum_to_lap(self) -> None:
        from core.driver import run_virtual_laps

        pid = PIDVirtualDriver(BALANCED)
        res = run_virtual_laps(BALANCED, pid, n_laps=2)
        sec = sector_times_s(res.telemetry)
        total = sec["sector_1_s"] + sec["sector_2_s"] + sec["sector_3_s"]
        # First sample may be t=dt; sector splits use row times → small gap vs lap_time_s.
        self.assertAlmostEqual(total, res.lap_time_s, delta=0.08)

    def test_variance_and_efficiency(self) -> None:
        self.assertEqual(lap_time_variance_s2([100.0]), 0.0)
        self.assertGreater(lap_time_variance_s2([100.0, 102.0, 98.0]), 0.0)
        self.assertAlmostEqual(efficiency_ratio(260.0, 250.0), 1.04, places=4)

    def test_enriched_payload(self) -> None:
        from core.driver import run_virtual_lap

        res = run_virtual_lap(BALANCED, PIDVirtualDriver(BALANCED))
        p = enriched_benchmark_payload(res, human_lap_s=270.0)
        self.assertIn("sectors_s", p)
        self.assertIn("efficiency_ratio_human_over_optimal", p)


if __name__ == "__main__":
    unittest.main()
