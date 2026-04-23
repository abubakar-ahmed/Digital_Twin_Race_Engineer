"""Delta engine: alignment, attribution, events."""

from __future__ import annotations

import unittest

from core.models import DriverInput
from core.simulation.tracks import BALANCED
from core.driver import PIDVirtualDriver, run_virtual_lap
from core.twin import DeltaReport, analyze_lap_delta
from core.events import EventKind


def _naive(_state):
    return DriverInput(0.78, 0.0, 0.0)


class TestDeltaEngine(unittest.TestCase):
    def test_human_slower_positive_total_delta(self) -> None:
        opt = run_virtual_lap(BALANCED, PIDVirtualDriver(BALANCED)).telemetry
        hum = run_virtual_lap(BALANCED, _naive).telemetry
        rep = analyze_lap_delta(hum, opt)
        self.assertIsInstance(rep, DeltaReport)
        self.assertGreater(rep.total_delta_time_s, 5.0)
        self.assertEqual(len(rep.sector_insights), 3)
        self.assertGreater(len(rep.aligned_samples), 10)

    def test_aligned_delta_t_matches_endpoints_order(self) -> None:
        opt = run_virtual_lap(BALANCED, PIDVirtualDriver(BALANCED)).telemetry
        hum = run_virtual_lap(BALANCED, _naive).telemetry
        rep = analyze_lap_delta(hum, opt, grid_step_m=100.0)
        last = rep.aligned_samples[-1]
        self.assertAlmostEqual(last["position"], rep.lap_length_m, delta=1.0)

    def test_events_have_kinds(self) -> None:
        opt = run_virtual_lap(BALANCED, PIDVirtualDriver(BALANCED)).telemetry
        hum = run_virtual_lap(BALANCED, _naive).telemetry
        rep = analyze_lap_delta(hum, opt)
        kinds = {e.kind for e in rep.events}
        self.assertTrue(kinds.issubset({EventKind.TIME_LOSS, EventKind.COACHING, EventKind.SETUP_HINT}))
        self.assertGreater(len(rep.events), 0)

    def test_to_dict_serializable_shape(self) -> None:
        opt = run_virtual_lap(BALANCED, PIDVirtualDriver(BALANCED)).telemetry
        hum = run_virtual_lap(BALANCED, _naive).telemetry
        d = analyze_lap_delta(hum, opt).to_dict()
        self.assertIn("sector_insights", d)
        self.assertTrue(all("cause" in s for s in d["sector_insights"]))


if __name__ == "__main__":
    unittest.main()
