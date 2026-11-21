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


# --- walk-forward folds ------------------------------------------------------
from src.split import walk_forward_folds  # noqa: E402

SMALL = {"n_folds": 3, "test_weeks": 8, "min_train_weeks": 10}


def test_folds_expand_and_test_blocks_do_not_overlap():
    folds = walk_forward_folds(_weeks(100), **SMALL)
    assert [f.number for f in folds] == [1, 2, 3]
    for prev, cur in zip(folds, folds[1:]):
        assert cur.train_end > prev.train_end
        assert cur.test_start == prev.test_end + pd.Timedelta(weeks=1)


def test_each_fold_has_purge_gap_and_full_test_block():
    for fold in walk_forward_folds(_weeks(100), **SMALL):
        assert (fold.test_start - fold.train_end).days // 7 - 1 == cfg.PURGE_GAP_WEEKS
        assert (fold.test_end - fold.test_start).days // 7 + 1 == SMALL["test_weeks"]
        assert fold.train_end + pd.Timedelta(weeks=max(cfg.HORIZONS)) < fold.test_start


def test_folds_stay_before_holdout():
    weeks = _weeks(100)
    folds = walk_forward_folds(weeks, **SMALL)
    assert folds[-1].test_end == holdout_split(weeks).train_end


def test_folds_need_minimum_training_weeks():
    with pytest.raises(ValueError, match="too few pre-holdout weeks"):
        walk_forward_folds(_weeks(40), **SMALL)


def test_default_folds_fit_real_data_length():
    folds = walk_forward_folds(_weeks(522))
    assert len(folds) == cfg.N_FOLDS
    assert all((f.test_end - f.test_start).days // 7 + 1 == cfg.FOLD_TEST_WEEKS for f in folds)
