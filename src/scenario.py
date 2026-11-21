"""What-if rainfall scenario (PRD 6.9): scale one ward's recent rain and re-forecast.

Only that ward's features are rebuilt (lags, windows, interactions), so it costs one row.
"""
from __future__ import annotations

import pandas as pd

from src import config as cfg
from src.features import build_features
from src.predict import ForecastError, predict_rows, rows_for

SCENARIO_WEEKS = 4  # "rainfall in the last 4 weeks"
MULTIPLIER_RANGE = (0.5, 2.0)


def scale_recent_rain(
    weekly: pd.DataFrame, ward: str, date, multiplier: float, weeks: int = SCENARIO_WEEKS
) -> pd.DataFrame:
    """Copy of `weekly` with `ward`'s rain multiplied in the `weeks` weeks ending at `date`."""
    end = pd.Timestamp(date)
    start = end - pd.Timedelta(weeks=weeks - 1)
    in_window = (weekly[cfg.WARD_COL] == ward) & weekly[cfg.DATE_COL].between(start, end)
    scaled = weekly[cfg.RAIN_COL].where(~in_window, weekly[cfg.RAIN_COL] * multiplier)
    return weekly.assign(**{cfg.RAIN_COL: scaled})


def _forecast(ward_weekly: pd.DataFrame, bundle: dict, date, horizon: int) -> dict:
    frame = build_features(ward_weekly, bundle["feature_params"])
    table, _ = predict_rows(rows_for(frame, bundle, date, horizon), bundle, horizon)
    row = table.iloc[0]
    return {key: row[key] for key in ("predicted_cases", "low_80", "high_80", "tier", "alert")}


def run_scenario(weekly: pd.DataFrame, bundle: dict, ward: str, date, horizon: int, multiplier: float) -> dict:
    """Baseline vs scenario forecast for one ward when its last 4 weeks of rain are scaled."""
    low, high = MULTIPLIER_RANGE
    if not low <= multiplier <= high:
        raise ForecastError(f"rain multiplier must be between {low} and {high}, got {multiplier}")
    ward_weekly = weekly[weekly[cfg.WARD_COL] == ward]
    if ward_weekly.empty:
        raise ForecastError(f"unknown ward: {ward}")
    baseline = _forecast(ward_weekly, bundle, date, horizon)
    scenario = _forecast(scale_recent_rain(ward_weekly, ward, date, multiplier), bundle, date, horizon)
    return {
        "multiplier": multiplier,
        "baseline": baseline,
        "scenario": scenario,
        "change_cases": round(float(scenario["predicted_cases"] - baseline["predicted_cases"]), 3),
    }
