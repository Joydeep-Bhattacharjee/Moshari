"""Constrained resource allocation (PRD 6.1): equity floor, then priority greedy.

Per resource (saline, kits), with stock = floor(stock_pct% x total need):

1. Equity floor: floor_w = ceil(floor_pct% x need_w), so no ward gets nothing.
   If the floors do not fit in the stock they are handed out one unit at a time by
   Webster (Sainte-Lague) quotients floor_w / (given_w + 0.5). Going unit by unit makes
   it house-monotone: less stock never gives any ward more. The PRD's largest-remainder
   rounding does not have that property (Alabama paradox), so it is not used.
2. Priority greedy: in priority order, each ward tops up to its need while stock lasts.
   This is the exact optimum of the LP  max sum(priority_w * x_w)  s.t.
   sum(x_w) <= stock - sum(floors), 0 <= x_w <= need_w - floor_w  (a fractional
   knapsack with unit weights); tests/test_allocate.py checks it against scipy HiGHS.

priority_w = 0.5 * risk_norm + 0.3 * density / densest + 0.2 * cases_w / max(cases),
ties broken by ward_id.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config as cfg

RISK_NORM = (0.25, 0.50, 0.75, 1.00)  # by tier index: Low, Medium, High, Critical
RISK_WEIGHT, DENSITY_WEIGHT, CASES_WEIGHT = 0.5, 0.3, 0.2
STOCK_PCT_RANGE = (30, 100)
DEFAULT_STOCK_PCT = 100
DEFAULT_FLOOR_PCT = 15
ALLOCATED_RESOURCES = (cfg.SALINE_COL, cfg.KITS_COL)  # beds are routed, not shipped
RESOURCE_UNITS = {cfg.SALINE_COL: ("saline", "bags"), cfg.KITS_COL: ("kits", "kits")}
CRITICAL_FILL = 0.5  # below this: CRITICAL for any ward
HIGH_RISK_FILL = 0.8  # below this: CRITICAL for High or Critical wards
HIGH_RISK_FROM = 2  # tier index of "High"
DEMAND_INPUT_COLS = (cfg.WARD_COL, cfg.CITY_COL, "cases", "risk_rank", cfg.DENSITY_COL, *ALLOCATED_RESOURCES)
ALLOCATION_COLS = (
    cfg.WARD_COL,
    cfg.CITY_COL,
    "resource",
    "priority",
    "priority_rank",
    "risk_rank",
    "need",
    "floor",
    "allocated",
    "fill",
    "deficit",
    "alert",
)


def _check_pct(name: str, value, low: int, high: int) -> int:
    if isinstance(value, bool) or not float(value).is_integer() or not low <= value <= high:
        raise ValueError(f"{name} must be a whole number from {low} to {high}, got {value}")
    return int(value)


def priority_scores(demand: pd.DataFrame, density_ref: float | None = None) -> pd.DataFrame:
    """Demand plus risk_norm, density_norm, cases_norm, priority and priority_rank (1 = first)."""
    missing = [c for c in DEMAND_INPUT_COLS if c not in demand.columns]
    if missing:
        raise ValueError(f"demand table is missing columns: {missing}")
    ref = float(density_ref if density_ref is not None else demand[cfg.DENSITY_COL].max())
    if ref <= 0:
        raise ValueError(f"density reference must be > 0, got {ref}")
    max_cases = float(demand["cases"].max())
    risk_norm = np.asarray(RISK_NORM)[demand["risk_rank"].astype(int).to_numpy()]
    density_norm = demand[cfg.DENSITY_COL].to_numpy(dtype=float) / ref
    cases_norm = demand["cases"].to_numpy(dtype=float) / max_cases if max_cases > 0 else np.zeros(len(demand))
    priority = RISK_WEIGHT * risk_norm + DENSITY_WEIGHT * density_norm + CASES_WEIGHT * cases_norm
    scored = demand.assign(
        risk_norm=risk_norm, density_norm=density_norm, cases_norm=cases_norm, priority=priority
    )
    order = scored.sort_values(["priority", cfg.WARD_COL], ascending=[False, True]).index
    return scored.assign(priority_rank=pd.Series(np.arange(1, len(order) + 1), index=order))


def stock_units(total_need: int, stock_pct) -> int:
    """floor(stock_pct% x total_need), in exact integer arithmetic."""
    pct = _check_pct("stock_pct", stock_pct, *STOCK_PCT_RANGE)
    return pct * int(total_need) // 100


def equity_floors(need: np.ndarray, floor_pct) -> np.ndarray:
    """ceil(floor_pct% x need) per ward, in exact integer arithmetic."""
    pct = _check_pct("floor_pct", floor_pct, 0, 100)
    return (pct * np.asarray(need, dtype=np.int64) + 99) // 100


def _fit_floors(floors: np.ndarray, stock: int) -> np.ndarray:
    """Floors as they are if they fit; else Webster-sequential shares that sum to stock."""
    if floors.sum() <= stock:
        return floors
    given = np.zeros_like(floors)
    for _ in range(stock):
        quotient = np.where(given < floors, floors / (given + 0.5), -np.inf)
        given[int(np.argmax(quotient))] += 1  # argmax takes the first max: priority order
    return given


def greedy_fill(capacity: np.ndarray, budget: int) -> np.ndarray:
    """Fill each slot in order up to its capacity until the budget runs out."""
    capacity = np.asarray(capacity, dtype=np.int64)
    used_before = np.concatenate(([0], np.cumsum(capacity)[:-1]))
    return np.clip(budget - used_before, 0, capacity)


def allocate_units(need: np.ndarray, stock: int, floor_pct) -> tuple[np.ndarray, np.ndarray]:
    """(floors, allocation) for wards given in priority order; allocation sums to stock."""
    need = np.asarray(need, dtype=np.int64)
    if (need < 0).any():
        raise ValueError("need must be >= 0")
    if not 0 <= stock <= need.sum():
        raise ValueError(f"stock must be from 0 to total need {need.sum()}, got {stock}")
    floors = _fit_floors(equity_floors(need, floor_pct), stock)
    return floors, floors + greedy_fill(need - floors, stock - int(floors.sum()))


def alert_levels(fill: np.ndarray, risk_rank: np.ndarray) -> np.ndarray:
    """CRITICAL: fill < 50%, or High+ risk and fill < 80%. WARNING: fill < 100%. Else OK."""
    fill, risk_rank = np.asarray(fill, dtype=float), np.asarray(risk_rank)
    critical = (fill < CRITICAL_FILL) | ((risk_rank >= HIGH_RISK_FROM) & (fill < HIGH_RISK_FILL))
    return np.where(critical, "CRITICAL", np.where(fill < 1.0, "WARNING", "OK"))


def _allocate_resource(ranked: pd.DataFrame, resource: str, stock_pct, floor_pct) -> pd.DataFrame:
    need = ranked[resource].to_numpy(dtype=np.int64)
    floors, alloc = allocate_units(need, stock_units(need.sum(), stock_pct), floor_pct)
    fill = np.divide(alloc, need, out=np.ones(len(need)), where=need > 0)
    return pd.DataFrame(
        {
            cfg.WARD_COL: ranked[cfg.WARD_COL].to_numpy(),
            cfg.CITY_COL: ranked[cfg.CITY_COL].to_numpy(),
            "resource": resource,
            "priority": ranked["priority"].to_numpy(),
            "priority_rank": ranked["priority_rank"].to_numpy(),
            "risk_rank": ranked["risk_rank"].to_numpy(),
            "need": need,
            "floor": floors,
            "allocated": alloc,
            "fill": fill,
            "deficit": need - alloc,
            "alert": alert_levels(fill, ranked["risk_rank"].to_numpy()),
        }
    )


def allocate(
    demand: pd.DataFrame,
    stock_pct=DEFAULT_STOCK_PCT,
    floor_pct=DEFAULT_FLOOR_PCT,
    density_ref: float | None = None,
) -> pd.DataFrame:
    """One row per ward per allocated resource, in priority order within each resource."""
    ranked = priority_scores(demand, density_ref).sort_values("priority_rank")
    parts = [_allocate_resource(ranked, r, stock_pct, floor_pct) for r in ALLOCATED_RESOURCES]
    return pd.concat(parts, ignore_index=True)[list(ALLOCATION_COLS)]


def region_summary(table: pd.DataFrame) -> dict:
    """Totals per resource, count of wards with any CRITICAL alert, and the region banner."""
    resources = {
        resource: {
            "need": int(rows["need"].sum()),
            "allocated": int(rows["allocated"].sum()),
            "short": int(rows["deficit"].sum()),
        }
        for resource, rows in table.groupby("resource", sort=False)
    }
    critical = int(table.loc[table["alert"] == "CRITICAL", cfg.WARD_COL].nunique())
    shortfalls = [
        f"{RESOURCE_UNITS[r][0]} short {totals['short']:,} {RESOURCE_UNITS[r][1]}"
        for r, totals in resources.items()
    ]
    return {
        "critical_wards": critical,
        "resources": resources,
        "banner": " · ".join([f"{critical} wards critical", *shortfalls]),
    }
