"""Per-ward dispatch notice fields, read straight from a ScenarioRun's tables (PRD 6.4).

Every number in an SMS, WhatsApp message or brief comes from a Notice, and a Notice is
built only from the allocation and routing tables, so the notices cannot disagree with
them (tests/test_dispatch.py cross-checks every ward). No LLM is involved.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src import config as cfg
from src.ops.capacity import CAPACITY_SOURCE

HIGH_RISK_FROM = 2  # tier index of "High": daily reporting from here up
ROUTINE = "Routine surveillance: no extra action needed this window."


@dataclass(frozen=True)
class WeekBand:
    target_week: str
    expected: float
    p10: float
    p90: float
    actual: float | None


@dataclass(frozen=True)
class Notice:
    ward_id: str
    city: str
    risk: str
    risk_rank: int
    cases_p50: int  # peak weekly expected cases in the window, rounded
    cases_p90: int  # peak weekly P90 in the window, rounded
    weeks: tuple[WeekBand, ...]
    saline_allocated: int
    saline_required: int
    kits_allocated: int
    kits_required: int
    beds_required: int
    beds_capacity: int
    capacity_source: str
    crews: int
    sends: tuple[tuple[str, int], ...]  # (to ward, patients)
    receives: tuple[tuple[str, int], ...]  # (from ward, patients)
    unplaced: int
    asof: str
    scenario_id: str
    generated_at: str

    @property
    def saline_short(self) -> int:
        return self.saline_required - self.saline_allocated

    @property
    def kits_short(self) -> int:
        return self.kits_required - self.kits_allocated

    @property
    def deficit(self) -> bool:
        return self.saline_short > 0 or self.kits_short > 0 or self.unplaced > 0


def display_cases(value: float) -> int:
    """Round a forecast for display, half up (floor(x + 0.5)), identical in Python and JS."""
    return int(math.floor(float(value) + 0.5))


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def actions(n: Notice) -> tuple[str, ...]:
    """Ordered action list for one ward, derived only from its notice fields."""
    steps = []
    if n.saline_short:
        steps.append(f"Request {plural(n.saline_short, 'more saline bag')} (emergency procurement).")
    if n.kits_short:
        steps.append(f"Request {plural(n.kits_short, 'more test kit')}.")
    steps += [f"Transfer {plural(k, 'patient')} to {ward} (same city)." for ward, k in n.sends]
    steps += [f"Prepare {plural(k, 'bed')} for patients from {ward}." for ward, k in n.receives]
    if n.unplaced:
        steps.append(
            f"Escalate: {plural(n.unplaced, 'patient')} without a bed in {n.city}; "
            "request field beds or regional support."
        )
    if n.crews:
        steps.append(f"Deploy {plural(n.crews, 'spray crew')} to clear standing water.")
    if n.risk_rank >= HIGH_RISK_FROM:
        steps.append("Report cases daily to the city health office.")
    return tuple(steps) or (ROUTINE,)


def _week_bands(rows: pd.DataFrame) -> tuple[WeekBand, ...]:
    return tuple(
        WeekBand(
            target_week=pd.Timestamp(r.target_week).date().isoformat(),
            expected=float(r.expected_cases),
            p10=float(r.p10_cases),
            p90=float(r.p90_cases),
            actual=None if pd.isna(r.actual_cases) else float(r.actual_cases),
        )
        for r in rows.itertuples()
    )


def _transfers(transfers: pd.DataFrame, side: str, ward: str, other: str) -> tuple[tuple[str, int], ...]:
    rows = transfers[transfers[side] == ward]
    return tuple((str(t), int(p)) for t, p in zip(rows[other], rows["patients"]))


def build_notices(run, generated_at: str) -> tuple[Notice, ...]:
    """One Notice per ward of a ScenarioRun, sorted by ward_id."""
    alloc = run.allocation.set_index([cfg.WARD_COL, "resource"])
    routing = run.routing.wards.set_index(cfg.WARD_COL)
    demand = run.demand.set_index(cfg.WARD_COL)
    transfers = run.routing.transfers
    asof = pd.Timestamp(run.scenario.asof).date().isoformat()
    notices = []
    for ward, rows in run.plan_window.sort_values("week_ahead").groupby(cfg.WARD_COL, sort=True):
        d, r = demand.loc[ward], routing.loc[ward]
        notices.append(
            Notice(
                ward_id=ward,
                city=str(d[cfg.CITY_COL]),
                risk=str(d["risk"]),
                risk_rank=int(d["risk_rank"]),
                cases_p50=display_cases(rows["expected_cases"].max()),
                cases_p90=display_cases(rows["p90_cases"].max()),
                weeks=_week_bands(rows),
                saline_allocated=int(alloc.loc[(ward, cfg.SALINE_COL), "allocated"]),
                saline_required=int(alloc.loc[(ward, cfg.SALINE_COL), "need"]),
                kits_allocated=int(alloc.loc[(ward, cfg.KITS_COL), "allocated"]),
                kits_required=int(alloc.loc[(ward, cfg.KITS_COL), "need"]),
                beds_required=int(r["required"]),
                beds_capacity=int(r["capacity"]),
                capacity_source=CAPACITY_SOURCE,
                crews=int(run.crews.get(ward, 0)),
                sends=_transfers(transfers, "from_ward", ward, "to_ward"),
                receives=_transfers(transfers, "to_ward", ward, "from_ward"),
                unplaced=int(r["unplaced"]),
                asof=asof,
                scenario_id=run.scenario_id,
                generated_at=generated_at,
            )
        )
    return tuple(notices)
