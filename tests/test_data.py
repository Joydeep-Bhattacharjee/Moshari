import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.data import GAP_FILLED_COL, fill_gaps, load_weekly, to_weekly


def test_weekly_input_passes_through_unchanged(weekly):
    result = to_weekly(weekly.assign(**{cfg.DATE_COL: weekly[cfg.DATE_COL].dt.strftime("%Y-%m-%d")}))
    pd.testing.assert_frame_equal(result, weekly, check_dtype=False)


def test_daily_rows_aggregate_to_monday_week(weekly):
    base = weekly.iloc[[0]]
    daily = pd.concat(
        [
            base.assign(**{cfg.DATE_COL: "2020-01-06", cfg.RAIN_COL: 5.0, cfg.TEMP_COL: 20.0,
                           cfg.TEMP_MAX_COL: 30.0, cfg.TARGET_COL: 1}),
            base.assign(**{cfg.DATE_COL: "2020-01-08", cfg.RAIN_COL: 7.0, cfg.TEMP_COL: 30.0,
                           cfg.TEMP_MAX_COL: 35.0, cfg.TARGET_COL: 2}),
        ],
        ignore_index=True,
    )
    row = to_weekly(daily).iloc[0]
    assert row[cfg.DATE_COL] == pd.Timestamp("2020-01-06")
    assert row[cfg.RAIN_COL] == 12.0
    assert row[cfg.TEMP_COL] == 25.0
    assert row[cfg.TEMP_MAX_COL] == 35.0
    assert row[cfg.TARGET_COL] == 3


def test_fill_gaps_inserts_missing_week_without_inventing_cases(weekly):
    missing_day = weekly[cfg.DATE_COL].iloc[5]
    with_gap = weekly[weekly[cfg.DATE_COL] != missing_day]
    filled = fill_gaps(with_gap)
    assert len(filled) == len(weekly)
    row = filled[(filled[cfg.WARD_COL] == "W0") & (filled[cfg.DATE_COL] == missing_day)].iloc[0]
    assert row[GAP_FILLED_COL]
    assert np.isnan(row[cfg.TARGET_COL])
    assert row[cfg.RAIN_COL] == pytest.approx(50.0)  # linear between weeks 4 and 6
    assert row[cfg.SANITATION_COL] == pytest.approx(0.7)
    assert filled[GAP_FILLED_COL].sum() == 2  # one per ward


def test_fill_gaps_on_complete_data_flags_nothing(weekly):
    assert not fill_gaps(weekly)[GAP_FILLED_COL].any()


@pytest.mark.skipif(not cfg.RAW_DATA_PATH.exists(), reason="raw data not present")
def test_real_data_is_complete_weekly_panel():
    weekly = load_weekly()
    assert len(weekly) == 60 * 522
    assert not weekly[GAP_FILLED_COL].any()
    assert (weekly[cfg.DATE_COL].dt.weekday == 0).all()
