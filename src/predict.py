"""Forecast every ward for a chosen week and horizon from the trained bundle (PRD 6.1).

All wards are predicted in one vectorized call; nothing here calls an external API.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from src import config as cfg
from src.data import load_weekly
from src.explain import GROUP_LABELS, MIN_IMPACT_CASES, driver_sentence, group_impacts
from src.features import FEATURE_COLS, build_features, target_col
from src.models import clip_interval
from src.tiers import ALERT_FROM_TIER, TIERS, assign_tiers

HISTORY_WEEKS_NEEDED = 8  # longest rain lag


class ForecastError(ValueError):
    """A forecast request the user can fix (unknown ward, week out of range, ...)."""


def load_bundle(path: Path = cfg.MODEL_PATH) -> dict:
    if not path.exists():
        raise ForecastError(f"model file not found: {path}. Run `python -m src.train` first.")
    bundle = joblib.load(path)
    if bundle["sklearn_version"] != sklearn.__version__:
        warnings.warn(
            f"model trained with scikit-learn {bundle['sklearn_version']}, running {sklearn.__version__}"
        )
    return bundle


def load_feature_frame(bundle: dict, path: Path = cfg.RAW_DATA_PATH) -> pd.DataFrame:
    """Features for every ward-week, using the thresholds learned at training time."""
    return build_features(load_weekly(path), bundle["feature_params"])


def valid_dates(frame: pd.DataFrame) -> list[pd.Timestamp]:
    """Forecast-origin weeks where every ward has full feature history."""
    complete = frame.dropna(subset=list(FEATURE_COLS))
    return sorted(pd.to_datetime(complete[cfg.DATE_COL].unique()))


def rows_for(frame: pd.DataFrame, bundle: dict, date, horizon: int) -> pd.DataFrame:
    """Feature rows for one forecast week; raises ForecastError for requests that cannot work."""
    if horizon not in bundle["models"]:
        raise ForecastError(f"horizon must be one of {sorted(bundle['models'])} weeks, got {horizon}")
    week = pd.Timestamp(date)
    rows = frame[frame[cfg.DATE_COL] == week]
    if rows.empty:
        first, last = frame[cfg.DATE_COL].min().date(), frame[cfg.DATE_COL].max().date()
        raise ForecastError(f"no data for week {week.date()}; pick a Monday from {first} to {last}")
    if rows[list(FEATURE_COLS)].isna().any().any():
        raise ForecastError(
            f"week {week.date()} is too early: forecasts need {HISTORY_WEEKS_NEEDED} weeks of history"
        )
    return rows


def _actual_tiers(actual: pd.Series, thresholds) -> list:
    tiers = assign_tiers(actual.fillna(0), thresholds)
    return [None if pd.isna(a) else TIERS[i] for a, i in zip(actual, tiers)]


def predict_rows(rows: pd.DataFrame, bundle: dict, horizon: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Forecast table and per-group driver impacts for the given feature rows."""
    models = bundle["models"][horizon]
    pred = models["point"].predict(rows)
    lo, hi = clip_interval(pred, models["q10"].predict(rows), models["q90"].predict(rows))
    thresholds = bundle["thresholds"][horizon]
    tier_idx = assign_tiers(pred, np.asarray(thresholds) * bundle["decision_scale"][horizon])
    impacts = group_impacts(models["point"], rows, bundle["train_medians"])
    top = impacts.idxmax(axis=1).where(impacts.max(axis=1) > MIN_IMPACT_CASES)
    actual = rows[target_col(horizon)]
    table = pd.DataFrame(
        {
            cfg.WARD_COL: rows[cfg.WARD_COL],
            cfg.CITY_COL: rows[cfg.CITY_COL],
            "forecast_week": rows[cfg.DATE_COL],
            "target_week": rows[cfg.DATE_COL] + pd.Timedelta(weeks=horizon),
            "predicted_cases": pred,
            "low_80": lo,
            "high_80": hi,
            "tier": [TIERS[i] for i in tier_idx],
            "tier_rank": tier_idx,
            "alert": tier_idx >= ALERT_FROM_TIER,
            "actual_cases": actual,
            "actual_tier": _actual_tiers(actual, thresholds),
            "top_driver": top.map(GROUP_LABELS).fillna("none"),
        },
        index=rows.index,
    )
    return table, impacts


def predict_all_wards(frame: pd.DataFrame, bundle: dict, date, horizon: int) -> pd.DataFrame:
    """Every ward for one week and horizon, Critical first, then by predicted cases."""
    table, _ = predict_rows(rows_for(frame, bundle, date, horizon), bundle, horizon)
    ranked = table.sort_values(["tier_rank", "predicted_cases"], ascending=False, ignore_index=True)
    return ranked.assign(rank=np.arange(1, len(ranked) + 1))


def predict_one(frame: pd.DataFrame, bundle: dict, ward: str, date, horizon: int) -> dict:
    """One ward's forecast, its driver impacts and a plain-language sentence."""
    rows = rows_for(frame, bundle, date, horizon)
    row = rows[rows[cfg.WARD_COL] == ward]
    if row.empty:
        raise ForecastError(f"unknown ward: {ward}")
    table, impacts = predict_rows(row, bundle, horizon)
    result = table.iloc[0].to_dict()
    drivers = impacts.iloc[0]
    return {
        **result,
        "impacts": drivers.round(3).to_dict(),
        "sentence": driver_sentence(result["tier"], horizon, drivers),
    }
