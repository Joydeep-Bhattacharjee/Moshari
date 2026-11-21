import numpy as np
import pandas as pd

from src import config as cfg
from src.baselines import (
    SEASON_WEEKS,
    SeasonalNaive,
    WardMean,
    add_seasonal_reference,
    seasonal_ref_col,
)


def test_ward_mean_predicts_training_mean_per_ward():
    frame = pd.DataFrame({cfg.WARD_COL: ["A", "A", "B"]})
    model = WardMean().fit(frame, pd.Series([2.0, 4.0, 10.0]))
    test = pd.DataFrame({cfg.WARD_COL: ["B", "A", "C"]})
    assert model.predict(test).tolist() == [10.0, 3.0, 16.0 / 3]  # unseen C -> overall mean


def test_seasonal_reference_is_same_ward_one_season_back(make_weekly):
    frame = add_seasonal_reference(make_weekly(n_wards=2, n_weeks=60))
    w1 = frame[frame[cfg.WARD_COL] == "W1"].reset_index(drop=True)
    for h in cfg.HORIZONS:
        lag = SEASON_WEEKS - h
        col = seasonal_ref_col(h)
        assert w1[col].iloc[:lag].isna().all(), "reference leaked across wards"
        assert w1.loc[lag + 1, col] == w1.loc[1, cfg.TARGET_COL]


def test_seasonal_reference_does_not_modify_input(make_weekly):
    weekly = make_weekly()
    snapshot = weekly.copy()
    add_seasonal_reference(weekly)
    pd.testing.assert_frame_equal(weekly, snapshot)


def test_seasonal_naive_uses_last_year_and_falls_back_to_ward_mean():
    col = seasonal_ref_col(3)
    train = pd.DataFrame({cfg.WARD_COL: ["A", "A"], col: [np.nan, np.nan]})
    model = SeasonalNaive(horizon=3).fit(train, pd.Series([4.0, 6.0]))
    test = pd.DataFrame({cfg.WARD_COL: ["A", "A"], col: [7.0, np.nan]})
    assert model.predict(test).tolist() == [7.0, 5.0]
