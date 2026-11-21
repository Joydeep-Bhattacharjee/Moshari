"""Baseline forecasters every model must beat (PRD section 6.5).

Models follow one protocol: fit(frame, y) -> self, predict(frame) -> array.
`frame` is a slice of the feature table (keys + features + seasonal references).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config as cfg

SEASON_WEEKS = 52  # 52 weeks back = same ISO week last year (off by one in 53-week years)


def seasonal_ref_col(horizon: int) -> str:
    return f"seasonal_ref_h{horizon}"


def add_seasonal_reference(features: pd.DataFrame) -> pd.DataFrame:
    """Add cases at week t+h-52 for each horizon: known at origin t because 52-h >= 0.

    Requires one row per ward per week, sorted by ward then date (as build_features returns).
    """
    cases_by_ward = features[cfg.TARGET_COL].groupby(features[cfg.WARD_COL])
    refs = {seasonal_ref_col(h): cases_by_ward.shift(SEASON_WEEKS - h) for h in cfg.HORIZONS}
    return features.assign(**refs)


class WardMean:
    """B1: each ward's mean training target; unseen wards get the overall mean."""

    def fit(self, frame: pd.DataFrame, y: pd.Series) -> "WardMean":
        self.ward_means_ = y.groupby(frame[cfg.WARD_COL]).mean().to_dict()
        self.overall_mean_ = float(y.mean())
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        means = frame[cfg.WARD_COL].map(self.ward_means_)
        return means.fillna(self.overall_mean_).to_numpy(dtype=float)


class SeasonalNaive:
    """B2: same ward, same week last year; falls back to the ward mean when that week is unknown."""

    def __init__(self, horizon: int):
        self.horizon = horizon

    def fit(self, frame: pd.DataFrame, y: pd.Series) -> "SeasonalNaive":
        self.fallback_ = WardMean().fit(frame, y)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        last_year = frame[seasonal_ref_col(self.horizon)].to_numpy(dtype=float)
        return np.where(np.isnan(last_year), self.fallback_.predict(frame), last_year)


BASELINES = {
    "B1_ward_mean": lambda horizon: WardMean(),
    "B2_seasonal_naive": SeasonalNaive,
}
