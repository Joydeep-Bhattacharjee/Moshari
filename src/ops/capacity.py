"""Bed capacity proxy per ward (PRD 3). Bed counts are not in the data, so they are derived.

capacity_w = P75 of the ward's non-zero weekly hospital_beds_required over the training
period (up to the model's train_end), taken as an observed count ('higher' quantile), so
holdout weeks never shape it. Labelled "proxy P75" wherever it is shown; real bed counts
can replace it.
"""
from __future__ import annotations

import pandas as pd

from src import config as cfg

CAPACITY_QUANTILE = 0.75
CAPACITY_SOURCE = "proxy P75"
CAPACITY_COLS = (cfg.WARD_COL, "capacity", "capacity_source")


def bed_capacity(history: pd.DataFrame, train_end) -> pd.DataFrame:
    """One row per ward with its proxy bed capacity; raises if a ward has no bed history."""
    dates = pd.to_datetime(history[cfg.DATE_COL], format="ISO8601")
    in_training = (dates <= pd.Timestamp(train_end)) & (history[cfg.BEDS_COL] > 0)
    capacity = (
        history[in_training]
        .groupby(cfg.WARD_COL)[cfg.BEDS_COL]
        .quantile(CAPACITY_QUANTILE, interpolation="higher")
    )
    wards = sorted(history[cfg.WARD_COL].unique())
    missing = [w for w in wards if w not in capacity.index]
    if missing:
        raise ValueError(f"no positive bed history up to {train_end} for wards: {missing[:5]}")
    return pd.DataFrame(
        {
            cfg.WARD_COL: wards,
            "capacity": capacity.loc[wards].astype(int).to_numpy(),
            "capacity_source": CAPACITY_SOURCE,
        }
    )
