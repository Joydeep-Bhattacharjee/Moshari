"""Forecast window: weekly cases for weeks +1..+H after an as-of week (PRD 5.1, 6.1).

The as-of week is the latest week whose data is known. The Phase 1 bundle has direct
models for h = 2, 3 and 4 weeks, so week +1 uses the h = 2 model from the week before
the as-of week. Every input is therefore known by the as-of week (leak-free), and no
new model is trained.
"""
from __future__ import annotations

import pandas as pd

from src import config as cfg
from src.predict import ForecastError, predict_rows, rows_for, valid_dates

MAX_WINDOW_WEEKS = 4
DEFAULT_WINDOW_WEEKS = 2
# week ahead -> (origin offset from the as-of week, in weeks; Phase 1 model horizon)
WINDOW_PLAN = {1: (-1, 2), 2: (0, 2), 3: (0, 3), 4: (0, 4)}
WINDOW_COLS = (
    cfg.WARD_COL,
    cfg.CITY_COL,
    "asof_week",
    "week_ahead",
    "target_week",
    "origin_week",
    "model_horizon",
    "expected_cases",
    "p10_cases",
    "p90_cases",
    "tier",
    "tier_rank",
    "top_driver",
    "actual_cases",
)


def _asof_week(frame: pd.DataFrame, asof) -> pd.Timestamp:
    dates = valid_dates(frame)
    first, last = dates[1], dates[-1]  # week +1 needs the week before the as-of week
    hint = f"pick a Monday from {first.date()} to {last.date()}"
    try:
        week = pd.Timestamp(asof)
    except (ValueError, TypeError) as exc:
        raise ForecastError(f"as-of week {asof!r} is not a date; {hint}") from exc
    if week not in set(dates[1:]):
        raise ForecastError(f"as-of week {week.date()} has no complete forecast inputs; {hint}")
    return week


def _one_week(frame: pd.DataFrame, bundle: dict, asof: pd.Timestamp, week_ahead: int) -> pd.DataFrame:
    offset, horizon = WINDOW_PLAN[week_ahead]
    origin = asof + pd.Timedelta(weeks=offset)
    table, _ = predict_rows(rows_for(frame, bundle, origin, horizon), bundle, horizon)
    return pd.DataFrame(
        {
            cfg.WARD_COL: table[cfg.WARD_COL],
            cfg.CITY_COL: table[cfg.CITY_COL],
            "asof_week": asof,
            "week_ahead": week_ahead,
            "target_week": table["target_week"],
            "origin_week": table["forecast_week"],
            "model_horizon": horizon,
            "expected_cases": table["predicted_cases"],
            "p10_cases": table["low_80"],
            "p90_cases": table["high_80"],
            "tier": table["tier"],
            "tier_rank": table["tier_rank"],
            "top_driver": table["top_driver"],
            "actual_cases": table["actual_cases"],
        }
    )


def forecast_window(
    frame: pd.DataFrame, bundle: dict, asof, weeks: int = DEFAULT_WINDOW_WEEKS
) -> pd.DataFrame:
    """One row per ward per week ahead (1..weeks), sorted by ward then week.

    `frame` is the Phase 1 feature frame (src.features.build_features). Raises
    ForecastError for a window length or as-of week that cannot be forecast.
    """
    if weeks not in WINDOW_PLAN:
        raise ForecastError(f"window must be 1 to {MAX_WINDOW_WEEKS} weeks, got {weeks}")
    week = _asof_week(frame, asof)
    parts = [_one_week(frame, bundle, week, k) for k in range(1, weeks + 1)]
    window = pd.concat(parts, ignore_index=True)
    return window.sort_values([cfg.WARD_COL, "week_ahead"], ignore_index=True)[list(WINDOW_COLS)]
