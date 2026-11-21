"""Chronological splits. Never random, never shuffled (PRD section 6.4)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src import config as cfg


@dataclass(frozen=True)
class HoldoutSplit:
    train_end: pd.Timestamp  # last forecast-origin week allowed in fitting
    holdout_start: pd.Timestamp  # first forecast-origin week of the final holdout


def holdout_split(dates: pd.Series) -> HoldoutSplit:
    """Last HOLDOUT_FRACTION of weeks is the holdout, preceded by PURGE_GAP_WEEKS unused weeks."""
    weeks = pd.Series(pd.to_datetime(pd.unique(dates))).sort_values(ignore_index=True)
    n_holdout = math.ceil(len(weeks) * cfg.HOLDOUT_FRACTION)
    n_train = len(weeks) - n_holdout - cfg.PURGE_GAP_WEEKS
    if n_train < 1:
        raise ValueError(f"too few weeks ({len(weeks)}) for a holdout with a purge gap")
    return HoldoutSplit(train_end=weeks[n_train - 1], holdout_start=weeks[len(weeks) - n_holdout])
