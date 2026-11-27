"""Forecast window over weeks +1..+4 from one as-of week, built on the Phase 1 bundle."""
import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.data import load_weekly
from src.features import build_features
from src.ops.forecast_window import WINDOW_COLS, forecast_window
from src.predict import ForecastError, load_bundle, predict_all_wards, valid_dates

pytestmark = pytest.mark.skipif(
    not (cfg.MODEL_PATH.exists() and cfg.ONSITE_DATA_PATH.exists()),
    reason="trained model or onsite data not present",
)

ASOF = pd.Timestamp("2025-06-30")  # PRD default: 2025 city-wide peak week
N_WARDS = 60
FORECAST_COLS = ["expected_cases", "p10_cases", "p90_cases", "tier_rank"]


@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


@pytest.fixture(scope="module")
def weekly():
    return load_weekly(cfg.ONSITE_DATA_PATH)


@pytest.fixture(scope="module")
def frame(weekly, bundle):
    return build_features(weekly, bundle["feature_params"])


@pytest.fixture(scope="module")
def window(frame, bundle):
    return forecast_window(frame, bundle, ASOF, 4)


def test_one_row_per_ward_per_week(window):
    assert list(window.columns) == list(WINDOW_COLS)
    assert len(window) == N_WARDS * 4
    weeks_per_ward = window.groupby(cfg.WARD_COL)["week_ahead"].apply(tuple)
    assert (weeks_per_ward == (1, 2, 3, 4)).all()


def test_target_week_is_asof_plus_week_ahead(window):
    expected = ASOF + pd.to_timedelta(window["week_ahead"] * 7, unit="D")
    assert (window["target_week"] == expected).all()
    assert (window["asof_week"] == ASOF).all()


def test_every_input_is_known_by_the_asof_week(window):
    assert (window["origin_week"] <= ASOF).all()
    gap = (window["target_week"] - window["origin_week"]).dt.days // 7
    assert (gap == window["model_horizon"]).all()


def test_week_plan_reuses_phase1_horizons(window):
    plan = window.groupby("week_ahead")["model_horizon"].unique().map(tuple).to_dict()
    assert plan == {1: (2,), 2: (2,), 3: (3,), 4: (4,)}


def test_intervals_are_ordered_and_non_negative(window):
    assert (window["p10_cases"] >= 0).all()
    assert (window["p10_cases"] <= window["expected_cases"]).all()
    assert (window["expected_cases"] <= window["p90_cases"]).all()


@pytest.mark.parametrize(
    ("week_ahead", "origin", "horizon"),
    [(1, ASOF - pd.Timedelta(weeks=1), 2), (3, ASOF, 3)],
)
def test_each_week_equals_the_phase1_forecast(frame, bundle, window, week_ahead, origin, horizon):
    phase1 = predict_all_wards(frame, bundle, origin, horizon).set_index(cfg.WARD_COL)
    ours = window[window["week_ahead"] == week_ahead].set_index(cfg.WARD_COL)
    np.testing.assert_allclose(ours["expected_cases"], phase1.loc[ours.index, "predicted_cases"])
    np.testing.assert_allclose(ours["p90_cases"], phase1.loc[ours.index, "high_80"])
    assert (ours["tier"] == phase1.loc[ours.index, "tier"]).all()


def test_data_after_the_asof_week_cannot_change_the_forecast(weekly, bundle, window):
    after = weekly[cfg.DATE_COL] > ASOF
    tampered = weekly.assign(
        **{
            cfg.RAIN_COL: weekly[cfg.RAIN_COL].where(~after, weekly[cfg.RAIN_COL] * 3 + 50),
            cfg.TEMP_COL: weekly[cfg.TEMP_COL].where(~after, weekly[cfg.TEMP_COL] + 3),
            cfg.TARGET_COL: weekly[cfg.TARGET_COL].where(~after, weekly[cfg.TARGET_COL] + 9),
        }
    )
    again = forecast_window(build_features(tampered, bundle["feature_params"]), bundle, ASOF, 4)
    pd.testing.assert_frame_equal(again[FORECAST_COLS], window[FORECAST_COLS])


def test_shorter_window_is_a_prefix_of_the_longer_one(frame, bundle, window):
    short = forecast_window(frame, bundle, ASOF, 2)
    assert set(short["week_ahead"]) == {1, 2}
    longer = window[window["week_ahead"] <= 2].reset_index(drop=True)
    pd.testing.assert_frame_equal(short, longer)


def test_actual_cases_come_from_the_dataset(window, weekly):
    truth = weekly.set_index([cfg.WARD_COL, cfg.DATE_COL])[cfg.TARGET_COL]
    keys = list(zip(window[cfg.WARD_COL], window["target_week"]))
    np.testing.assert_array_equal(window["actual_cases"].to_numpy(), truth.loc[keys].to_numpy())


def test_actuals_are_missing_beyond_the_data_end(frame, bundle):
    last = forecast_window(frame, bundle, "2025-12-29", 1)
    assert last["actual_cases"].isna().all()
    assert (last["target_week"] == pd.Timestamp("2026-01-05")).all()


def test_first_possible_asof_week_works(frame, bundle):
    first = valid_dates(frame)[1]
    assert len(forecast_window(frame, bundle, first, 1)) == N_WARDS


@pytest.mark.parametrize("weeks", [0, 5])
def test_window_length_outside_1_to_4_is_rejected(frame, bundle, weeks):
    with pytest.raises(ForecastError, match="1 to 4"):
        forecast_window(frame, bundle, ASOF, weeks)


@pytest.mark.parametrize("asof", ["2016-01-04", "2025-06-29", "2026-01-05", "not-a-date"])
def test_unusable_asof_week_is_rejected(frame, bundle, asof):
    with pytest.raises(ForecastError, match="as-of"):
        forecast_window(frame, bundle, asof, 2)


def test_same_request_gives_identical_output(frame, bundle, window):
    pd.testing.assert_frame_equal(forecast_window(frame, bundle, ASOF, 4), window)
