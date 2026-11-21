"""Chronological splits. Never random, never shuffled (PRD section 6.4).

Holdout: the last HOLDOUT_FRACTION of weeks, after a purge gap, touched once.
Walk-forward: N_FOLDS expanding-window folds on the weeks before the holdout.
Fold i trains on weeks <= train_end, skips PURGE_GAP_WEEKS, tests on the next block.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src import config as cfg


@dataclass(frozen=True)
class HoldoutSplit:
    train_end: pd.Timestamp  # last forecast-origin week allowed in fitting
    holdout_start: pd.Timestamp  # first forecast-origin week of the final holdout


@dataclass(frozen=True)
class Fold:
    number: int
    train_end: pd.Timestamp  # last training forecast-origin week
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def _sorted_weeks(dates: pd.Series) -> pd.Series:
    return pd.Series(pd.to_datetime(pd.unique(dates))).sort_values(ignore_index=True)


def holdout_split(dates: pd.Series) -> HoldoutSplit:
    """Last HOLDOUT_FRACTION of weeks is the holdout, preceded by PURGE_GAP_WEEKS unused weeks."""
    weeks = _sorted_weeks(dates)
    n_holdout = math.ceil(len(weeks) * cfg.HOLDOUT_FRACTION)
    n_train = len(weeks) - n_holdout - cfg.PURGE_GAP_WEEKS
    if n_train < 1:
        raise ValueError(f"too few weeks ({len(weeks)}) for a holdout with a purge gap")
    return HoldoutSplit(train_end=weeks[n_train - 1], holdout_start=weeks[len(weeks) - n_holdout])


def walk_forward_folds(
    dates: pd.Series,
    n_folds: int = cfg.N_FOLDS,
    test_weeks: int = cfg.FOLD_TEST_WEEKS,
    min_train_weeks: int = cfg.MIN_TRAIN_WEEKS,
) -> tuple[Fold, ...]:
    """Back-to-back test blocks ending at the holdout's train_end; each fold's train set expands."""
    weeks = _sorted_weeks(dates)
    weeks = weeks[weeks <= holdout_split(dates).train_end].reset_index(drop=True)
    first_test = len(weeks) - n_folds * test_weeks
    if first_test - cfg.PURGE_GAP_WEEKS < min_train_weeks:
        raise ValueError(
            f"too few pre-holdout weeks ({len(weeks)}) for {n_folds} folds of {test_weeks} weeks"
        )
    starts = [first_test + i * test_weeks for i in range(n_folds)]
    return tuple(
        Fold(
            number=i + 1,
            train_end=weeks[start - cfg.PURGE_GAP_WEEKS - 1],
            test_start=weeks[start],
            test_end=weeks[start + test_weeks - 1],
        )
        for i, start in enumerate(starts)
    )
