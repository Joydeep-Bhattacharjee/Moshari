"""Forecast fallback chain (PRD 6.5): model -> cached forecast -> seasonal-mean baseline.

1. model     the Phase 1 bundle, through forecast_window.
2. cache     public/data/ops/forecasts.json, the same model output exported earlier.
3. seasonal  each ward's mean cases in the same ISO week of earlier years, using only
             weeks up to the as-of date. Needs nothing but the data, so it always works.

The chain only steps down when the model cannot be loaded. A request that cannot be
forecast (for example an as-of week that is not a Monday in the data) is the user's
error and raises ForecastError instead of silently switching source. Every result says
which source produced it and why, so the UI can label it.
"""
from __future__ import annotations

import json
import pickle
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src import config as cfg
from src.ops.forecast_window import WINDOW_COLS, WINDOW_PLAN, forecast_window
from src.predict import ForecastError
from src.tiers import TIERS, assign_tiers

# Training-period P50 / P75 / P90 of positive weekly cases (docs/data_audit.md section 6);
# used only when no model bundle is available to supply its own thresholds.
FALLBACK_THRESHOLDS = (5.0, 9.0, 14.0)
SEASONAL_QUANTILES = (0.10, 0.90)
MODEL_LOAD_ERRORS = (ForecastError, OSError, EOFError, pickle.UnpicklingError, ImportError, KeyError, ValueError)


@dataclass(frozen=True)
class ResilientForecast:
    window: pd.DataFrame
    source: str  # "model" | "cache" | "seasonal"
    reason: str  # why this source was used


def _actuals(weekly: pd.DataFrame) -> pd.Series:
    return weekly.set_index([cfg.WARD_COL, cfg.DATE_COL])[cfg.TARGET_COL]


def _frame(rows: list[dict], weekly: pd.DataFrame) -> pd.DataFrame:
    """Rows -> a window table with WINDOW_COLS; tiers from FALLBACK_THRESHOLDS if not given."""
    table = pd.DataFrame(rows)
    if "tier_rank" in table:
        tier_rank = table["tier_rank"].to_numpy(dtype=int)
    else:
        tier_rank = assign_tiers(table["expected_cases"], FALLBACK_THRESHOLDS)
    actual = _actuals(weekly).reindex(list(zip(table[cfg.WARD_COL], table["target_week"])))
    return table.assign(
        tier_rank=np.asarray(tier_rank, dtype=int),
        tier=[TIERS[int(i)] for i in tier_rank],
        actual_cases=actual.to_numpy(dtype=float),
    ).sort_values([cfg.WARD_COL, "week_ahead"], ignore_index=True)[list(WINDOW_COLS)]


def seasonal_window(weekly: pd.DataFrame, asof, weeks: int) -> pd.DataFrame:
    """Same-ISO-week mean of earlier years per ward, from weeks up to the as-of date only."""
    asof = pd.Timestamp(asof)
    history = weekly[weekly[cfg.DATE_COL] <= asof]
    iso_week = history[cfg.DATE_COL].dt.isocalendar().week.astype(int)
    by_week = history.assign(_iso=iso_week).groupby([cfg.WARD_COL, "_iso"])[cfg.TARGET_COL]
    mean, low, high = by_week.mean(), by_week.quantile(SEASONAL_QUANTILES[0]), by_week.quantile(SEASONAL_QUANTILES[1])
    cities = weekly.groupby(cfg.WARD_COL)[cfg.CITY_COL].first()
    rows = []
    for k in range(1, weeks + 1):
        target = asof + pd.Timedelta(weeks=k)
        week = int(target.isocalendar().week)
        for ward in sorted(cities.index):
            key = (ward, week) if (ward, week) in mean.index else (ward, min(week, 52))
            expected = float(mean.get(key, 0.0))
            rows.append(
                {
                    cfg.WARD_COL: ward,
                    cfg.CITY_COL: cities[ward],
                    "asof_week": asof,
                    "week_ahead": k,
                    "target_week": target,
                    "origin_week": asof,
                    "model_horizon": 0,
                    "expected_cases": expected,
                    "p10_cases": min(float(low.get(key, 0.0)), expected),
                    "p90_cases": max(float(high.get(key, 0.0)), expected),
                    "top_driver": "season",
                }
            )
    return _frame(rows, weekly)


def cached_window(cache_path: Path, asof, weeks: int, weekly: pd.DataFrame) -> pd.DataFrame:
    """The exported model forecast for one as-of week; raises LookupError if absent."""
    path = Path(cache_path)
    if not path.exists():
        raise LookupError(f"no forecast cache at {path}")
    cache = json.loads(path.read_text(encoding="utf-8"))
    asof = pd.Timestamp(asof)
    windows = cache["windows"].get(asof.date().isoformat())
    if windows is None:
        raise LookupError(f"forecast cache has no as-of week {asof.date()}")
    cities = weekly.groupby(cfg.WARD_COL)[cfg.CITY_COL].first()
    labels = cache["driver_labels"]
    rows = [
        {
            cfg.WARD_COL: ward,
            cfg.CITY_COL: cities[ward],
            "asof_week": asof,
            "week_ahead": k,
            "target_week": asof + pd.Timedelta(weeks=k),
            "origin_week": asof + pd.Timedelta(weeks=WINDOW_PLAN[k][0]),
            "model_horizon": WINDOW_PLAN[k][1],
            "expected_cases": block["expected"][k - 1],
            "p10_cases": block["p10"][k - 1],
            "p90_cases": block["p90"][k - 1],
            "tier_rank": block["tier_rank"][k - 1],
            "top_driver": labels[block["top_driver"][k - 1]],
        }
        for ward, block in sorted(windows.items())
        for k in range(1, weeks + 1)
    ]
    return _frame(rows, weekly)


def resilient_window(
    asof, weeks: int, *, load_model: Callable[[], tuple], cache_path: Path, weekly: pd.DataFrame
) -> ResilientForecast:
    """Forecast window from the best available source, with the source and reason."""
    try:
        frame, bundle = load_model()
    except MODEL_LOAD_ERRORS as model_error:
        reason = f"model unavailable ({model_error})"
        try:
            return ResilientForecast(cached_window(cache_path, asof, weeks, weekly), "cache", reason)
        except (LookupError, OSError, ValueError) as cache_error:
            reason = f"{reason}; cache unavailable ({cache_error})"
            return ResilientForecast(seasonal_window(weekly, asof, weeks), "seasonal", reason)
    return ResilientForecast(forecast_window(frame, bundle, asof, weeks), "model", "model loaded")
