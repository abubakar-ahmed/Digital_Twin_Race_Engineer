"""Human vs optimal: aligned deltas, causal attribution, DIL events."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from core.events.models import DILEvent, EventKind
from core.optimization.metrics import sector_times_s
from core.simulation.constants import TRACK_LENGTH

from core.twin.alignment import align_traces, sort_by_position

Row = dict[str, float]


def _brake_onset_position_m(
    trace: list[Row],
    lap_length: float,
    f_lo: float,
    f_hi: float,
    threshold: float = 0.14,
) -> float | None:
    """First position (m) where brake exceeds threshold in lap fraction band."""
    if lap_length <= 0:
        return None
    p0, p1 = f_lo * lap_length, f_hi * lap_length
    h = sort_by_position(trace)
    for r in h:
        pos = float(r["position"])
        if p0 <= pos <= p1 and float(r.get("brake", 0.0)) >= threshold:
            return pos
    return None


def _mean_abs(rows: list[Row], key: str) -> float:
    if not rows or key not in rows[0]:
        return 0.0
    return float(mean(abs(float(r[key])) for r in rows))


def _mean_key(rows: list[Row], key: str) -> float:
    if not rows or key not in rows[0]:
        return 0.0
    return _mean(rows, key)


def _lap_time_s(trace: list[Row]) -> float:
    if not trace:
        return 0.0
    return float(trace[-1]["time"])


def _rows_in_position_band(aligned: list[Row], p0: float, p1: float) -> list[Row]:
    return [r for r in aligned if p0 <= float(r["position"]) <= p1]


def _mean(rows: list[Row], key: str) -> float:
    if not rows:
        return 0.0
    return float(mean(float(r[key]) for r in rows))


@dataclass(slots=True)
class SectorInsight:
    corner: str
    sector_index: int
    delta_time_s: float
    mean_delta_speed_m_s: float
    mean_tire_wear_delta: float
    cause: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        cause_label = self.cause.replace("_", " ")
        return {
            "corner": self.corner,
            "sector_index": self.sector_index,
            "delta_time": self.delta_time_s,
            "mean_delta_speed_m_s": self.mean_delta_speed_m_s,
            "mean_tire_wear_delta": self.mean_tire_wear_delta,
            "cause": cause_label,
            "cause_id": self.cause,
            "recommendation": self.recommendation,
        }


@dataclass(slots=True)
class DeltaReport:
    """Full delta analysis for one lap comparison."""

    lap_length_m: float
    human_lap_time_s: float
    optimal_lap_time_s: float
    total_delta_time_s: float
    aligned_samples: list[dict[str, float]]
    sector_insights: list[SectorInsight]
    events: list[DILEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lap_length_m": self.lap_length_m,
            "human_lap_time_s": self.human_lap_time_s,
            "optimal_lap_time_s": self.optimal_lap_time_s,
            "total_delta_time_s": self.total_delta_time_s,
            "aligned_samples": self.aligned_samples,
            "sector_insights": [s.to_dict() for s in self.sector_insights],
            "events": [
                {"kind": e.kind.value, "message": e.message, "payload": e.payload} for e in self.events
            ],
        }


def _attribute_sector(
    si: int,
    corner: str,
    sector_delta_t: float,
    aligned: list[Row],
    lap_length: float,
    *,
    brake_human_m: float | None = None,
    brake_opt_m: float | None = None,
) -> SectorInsight:
    f_lo = (0.0, 0.30, 0.60)[si]
    f_hi = (0.30, 0.60, 1.0)[si]
    p0, p1 = f_lo * lap_length, f_hi * lap_length
    band = _rows_in_position_band(aligned, p0, p1)
    mdv = _mean(band, "delta_v")
    mtd = _mean(band, "human_tire_wear") - _mean(band, "optimal_tire_wear")

    # Braking window (end of straight → early corner)
    brake_win = _rows_in_position_band(aligned, 0.26 * lap_length, 0.36 * lap_length)
    carry_speed = _mean(brake_win, "human_speed") - _mean(brake_win, "optimal_speed")

    # Exit / traction window (mid-late lap)
    exit_win = _rows_in_position_band(aligned, 0.55 * lap_length, 0.78 * lap_length)
    exit_deficit = _mean(exit_win, "delta_v")
    exit_d_th = _mean_key(exit_win, "delta_throttle")
    exit_h_st = _mean_abs(exit_win, "human_steering")
    exit_o_st = _mean_abs(exit_win, "optimal_steering")

    late_by_axes = (
        brake_human_m is not None
        and brake_opt_m is not None
        and brake_human_m > brake_opt_m + 10.0
        and carry_speed > 1.2
    )

    cause = "balanced"
    rec = "Maintain current approach in this sector."

    if si == 0:
        if sector_delta_t > 0.04 and mdv > 1.6:
            cause = "conservative_driving"
            rec = "Not extracting full grip on the straight — build throttle earlier within safe margin."
        elif sector_delta_t > 0.04:
            cause = "time_loss"
            rec = "Review line and throttle trace vs reference on sector T1."
    elif si == 1:
        if (
            (late_by_axes and sector_delta_t > 0.02)
            or (carry_speed > 2.2 and sector_delta_t > 0.03)
        ):
            cause = "late_braking"
            rec = "Brake earlier by ~5–15 m before corner entry; trail brake into apex."
        elif (
            sector_delta_t > 0.03
            and _mean_key(band, "human_throttle") > 0.72
            and _mean_abs(band, "human_steering") > 0.22
            and mtd > 0.025
        ):
            cause = "overdriving"
            rec = "High steering + throttle with tire cost — unwind steering before picking up throttle."
        elif mtd > 0.035 and sector_delta_t > 0.03:
            cause = "tire_overuse"
            rec = "Reduce combined brake/throttle spikes in T2 to preserve rear grip."
        elif sector_delta_t > 0.04 and mdv > 1.8:
            cause = "conservative_driving"
            rec = "Carrying too little mid-corner speed vs reference — use progressive throttle."
        elif sector_delta_t > 0.02:
            cause = "time_loss"
            rec = "Compare minimum speed and lateral load proxy (steering) vs optimal trace."
    else:
        poor_exit_adv = (
            exit_d_th > 0.1
            and exit_h_st > exit_o_st + 0.06
            and exit_deficit > 1.8
            and sector_delta_t > 0.03
        )
        if (exit_deficit > 2.6 and sector_delta_t > 0.03) or poor_exit_adv:
            cause = "poor_exit_throttle"
            rec = "Poor throttle application on exit — pick up power earlier where grip allows."
        elif mtd > 0.04 and sector_delta_t > 0.03:
            cause = "tire_overuse"
            rec = "Overdriving tires in final sector — soften inputs to protect exit traction."
        elif sector_delta_t > 0.04 and mdv > 1.5:
            cause = "conservative_driving"
            rec = "Leaving time on table in T3 — align top speed with reference envelope."
        elif sector_delta_t > 0.02:
            cause = "time_loss"
            rec = "Delta concentrated late lap — check braking points into slow sections."

    return SectorInsight(
        corner=corner,
        sector_index=si + 1,
        delta_time_s=sector_delta_t,
        mean_delta_speed_m_s=mdv,
        mean_tire_wear_delta=mtd,
        cause=cause,
        recommendation=rec,
    )


def insights_to_events(insights: list[SectorInsight]) -> list[DILEvent]:
    """Map structured insights to TIME_LOSS / COACHING / SETUP_HINT events."""
    events: list[DILEvent] = []
    for ins in insights:
        if ins.delta_time_s > 0.02:
            events.append(
                DILEvent(
                    kind=EventKind.TIME_LOSS,
                    message=f"{ins.corner}: +{ins.delta_time_s:.2f}s vs optimal",
                    payload=ins.to_dict(),
                )
            )
        if ins.cause in ("late_braking", "poor_exit_throttle", "conservative_driving", "overdriving"):
            events.append(
                DILEvent(
                    kind=EventKind.COACHING,
                    message=f"{ins.corner}: {ins.cause.replace('_', ' ')}",
                    payload=ins.to_dict(),
                )
            )
        if ins.cause == "tire_overuse":
            events.append(
                DILEvent(
                    kind=EventKind.SETUP_HINT,
                    message=f"{ins.corner}: tire limited performance",
                    payload=ins.to_dict(),
                )
            )
    return events


def analyze_lap_delta(
    human: list[Row],
    optimal: list[Row],
    *,
    lap_length: float = TRACK_LENGTH,
    grid_step_m: float = 50.0,
) -> DeltaReport:
    """
    Align by distance, compute Δt and Δv, sector losses, rule-based causes, and events.
    """
    if not human or not optimal:
        raise ValueError("human and optimal telemetry must be non-empty")

    human_lt = _lap_time_s(human)
    opt_lt = _lap_time_s(optimal)
    total_dt = human_lt - opt_lt

    aligned = align_traces(human, optimal, lap_length=lap_length, step_m=grid_step_m)

    bh = _brake_onset_position_m(human, lap_length, 0.14, 0.44)
    bo = _brake_onset_position_m(optimal, lap_length, 0.14, 0.44)

    hs = sector_times_s(human, lap_length=lap_length)
    os_ = sector_times_s(optimal, lap_length=lap_length)
    keys = ("sector_1_s", "sector_2_s", "sector_3_s")
    corners = ("T1", "T2", "T3")
    insights: list[SectorInsight] = []
    for i, k in enumerate(keys):
        dsec = float(hs[k]) - float(os_[k])
        insights.append(
            _attribute_sector(
                i,
                corners[i],
                dsec,
                aligned,
                lap_length,
                brake_human_m=bh,
                brake_opt_m=bo,
            )
        )

    events = insights_to_events(insights)

    return DeltaReport(
        lap_length_m=lap_length,
        human_lap_time_s=human_lt,
        optimal_lap_time_s=opt_lt,
        total_delta_time_s=total_dt,
        aligned_samples=aligned,
        sector_insights=insights,
        events=events,
    )
