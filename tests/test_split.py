import pandas as pd
import pytest

from src import config as cfg
from src.split import holdout_split


def _weeks(n: int) -> pd.Series:
    return pd.Series(pd.date_range("2020-01-06", periods=n, freq=cfg.DATA_FREQ))


def test_purge_gap_separates_train_and_holdout():
    split = holdout_split(_weeks(100))
    gap_weeks = (split.holdout_start - split.train_end).days // 7 - 1
    assert gap_weeks == cfg.PURGE_GAP_WEEKS


def test_train_targets_never_reach_holdout():
    split = holdout_split(_weeks(100))
    last_train_target = split.train_end + pd.Timedelta(weeks=max(cfg.HORIZONS))
    assert last_train_target < split.holdout_start


def test_holdout_is_last_fraction_of_weeks():
    weeks = _weeks(100)
    split = holdout_split(weeks)
    assert (weeks >= split.holdout_start).sum() == 15


def test_handles_unsorted_repeated_dates():
    weeks = _weeks(100)
    shuffled = pd.concat([weeks, weeks]).sample(frac=1, random_state=0)
    assert holdout_split(shuffled) == holdout_split(weeks)


def test_too_few_weeks_raises():
    with pytest.raises(ValueError, match="too few weeks"):
        holdout_split(_weeks(5))


def test_purge_gap_covers_longest_horizon():
    assert cfg.PURGE_GAP_WEEKS >= max(cfg.HORIZONS)
