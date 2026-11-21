import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.backtest import fold_frames, run_backtest, summarize
from src.baselines import WardMean
from src.features import target_col
from src.split import walk_forward_folds

SMALL = {"n_folds": 2, "test_weeks": 6, "min_train_weeks": 10}


@pytest.fixture
def frames(make_weekly):
    weekly = make_weekly(n_wards=2, n_weeks=60)
    return fold_frames(weekly, walk_forward_folds(weekly[cfg.DATE_COL], **SMALL))


class SpyZero:
    """Predicts 0 and records which origin weeks it was trained and tested on."""

    seen: list = []

    def fit(self, frame, y):
        SpyZero.seen.append(("train", frame[cfg.DATE_COL].max(), y.isna().any()))
        return self

    def predict(self, frame):
        SpyZero.seen.append(("test", frame[cfg.DATE_COL].min(), None))
        return np.zeros(len(frame))


def test_models_train_only_before_purge_gap(frames):
    SpyZero.seen = []
    run_backtest(lambda h: SpyZero(), 2, frames)
    for (fold, _), i in zip(frames, range(0, len(SpyZero.seen), 2)):
        _, train_max, has_nan = SpyZero.seen[i]
        _, test_min, _ = SpyZero.seen[i + 1]
        assert train_max <= fold.train_end
        assert test_min >= fold.test_start
        assert not has_nan


def test_metrics_match_manual_errors(frames):
    result = run_backtest(lambda h: SpyZero(), 3, frames, name="zero")
    for fold, frame in frames:
        y = frame.loc[frame[cfg.DATE_COL].between(fold.test_start, fold.test_end), target_col(3)].dropna()
        row = result.metrics[result.metrics["fold"] == fold.number].iloc[0]
        assert row["mae"] == pytest.approx(y.abs().mean())
        assert row["rmse"] == pytest.approx(np.sqrt((y**2).mean()))
        assert row["n_test"] == len(y)


def test_predictions_cover_each_test_row_once(frames):
    result = run_backtest(lambda h: WardMean(), 2, frames, name="B1")
    assert not result.predictions.duplicated([cfg.WARD_COL, cfg.DATE_COL, "fold"]).any()
    assert len(result.predictions) == result.metrics["n_test"].sum()
    assert set(result.predictions["model"]) == {"B1"}


def test_summarize_averages_folds():
    metrics = pd.DataFrame(
        {"model": ["m", "m"], "horizon": [2, 2], "mae": [1.0, 3.0], "rmse": [2.0, 4.0]}
    )
    row = summarize(metrics).iloc[0]
    assert (row["mae"], row["rmse"]) == (2.0, 3.0)
