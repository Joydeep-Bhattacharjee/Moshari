"""Supply demand per ward from a forecast window (PRD 6.1), using the dataset's own formulas.

units = round_half_down(cases * per_1000 / 1000), applied to each week's forecast.
Half-down is what the dataset does on all 31,320 rows (docs/data_audit.md section 8);
the PRD's round-half-up breaks 1,197 bed rows.

Over a window of weeks, saline and kits add up (they are consumed each week) while beds
take the peak week (a bed is reused once a patient leaves).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config as cfg
from src.tiers import TIERS

# Planning Confidence -> forecast column it plans on.
CONFIDENCE_COLS = {"likely": "expected_cases", "bad": "p90_cases"}
DEFAULT_CONFIDENCE = "likely"
WINDOW_INPUT_COLS = (cfg.WARD_COL, cfg.CITY_COL, "week_ahead", "tier_rank", *CONFIDENCE_COLS.values())
DEMAND_COLS = (
    cfg.WARD_COL,
    cfg.CITY_COL,
    "confidence",
    "window_weeks",
    "cases",
    "peak_weekly_cases",
    *cfg.SUPPLY_COLS,
    "risk",
    "risk_rank",
)


def supply_units(cases, per_1000: int) -> np.ndarray:
    """Whole units for each case count: round_half_down(max(cases, 0) * per_1000 / 1000).

    ceil(v - 0.5) is half-down rounding. For integer counts it is exact, because every
    v = n / 1000 is either an exact .5 tie in binary or at least 0.0005 away from one.
    """
    if per_1000 < 0:
        raise ValueError(f"per_1000 must be >= 0, got {per_1000}")
    values = np.asarray(cases, dtype=float)
    if np.isnan(values).any():
        raise ValueError("case counts contain NaN")
    scaled = np.clip(values, 0.0, None) * per_1000 / 1000
    return np.ceil(scaled - 0.5).astype(np.int64)


def _check_window(window: pd.DataFrame, confidence: str) -> str:
    if confidence not in CONFIDENCE_COLS:
        raise ValueError(f"confidence must be one of {sorted(CONFIDENCE_COLS)}, got {confidence!r}")
    missing = [c for c in WINDOW_INPUT_COLS if c not in window.columns]
    if missing:
        raise ValueError(f"forecast window is missing columns: {missing}")
    if window.empty:
        raise ValueError("forecast window is empty")
    return CONFIDENCE_COLS[confidence]


def ward_demand(window: pd.DataFrame, confidence: str = DEFAULT_CONFIDENCE) -> pd.DataFrame:
    """One row per ward: planned cases and saline / kits / beds needed over the window.

    Risk is the highest weekly tier in the window, from the expected forecast; the
    Planning Confidence only changes how much is planned, not the risk label.
    """
    cases_col = _check_window(window, confidence)
    cases = window[cases_col].clip(lower=0)
    weekly = pd.DataFrame(
        {
            cfg.WARD_COL: window[cfg.WARD_COL],
            cfg.CITY_COL: window[cfg.CITY_COL],
            "week_ahead": window["week_ahead"],
            "tier_rank": window["tier_rank"],
            "cases": cases,
            **{col: supply_units(cases, cfg.SUPPLY_PER_1000_CASES[col]) for col in cfg.SUPPLY_COLS},
        }
    )
    grouped = weekly.groupby([cfg.WARD_COL, cfg.CITY_COL], sort=True)
    demand = grouped.agg(
        window_weeks=("week_ahead", "nunique"),
        cases=("cases", "sum"),
        peak_weekly_cases=("cases", "max"),
        **{cfg.SALINE_COL: (cfg.SALINE_COL, "sum")},
        **{cfg.KITS_COL: (cfg.KITS_COL, "sum")},
        **{cfg.BEDS_COL: (cfg.BEDS_COL, "max")},
        risk_rank=("tier_rank", "max"),
    ).reset_index()
    return demand.assign(
        confidence=confidence,
        risk=demand["risk_rank"].map(lambda i: TIERS[int(i)]),
    )[list(DEMAND_COLS)]
