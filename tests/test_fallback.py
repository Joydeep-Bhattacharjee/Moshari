"""Forecast fallback chain (PRD 6.5): model -> cached forecast -> seasonal-mean baseline."""
import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.data import load_weekly
from src.features import build_features
from src.ops.fallback import resilient_window, seasonal_window
from src.ops.forecast_window import WINDOW_COLS, forecast_window
from src.ops.ui_export import OUT_DIR
from src.predict import ForecastError, load_bundle

pytestmark = pytest.mark.skipif(
    not (cfg.MODEL_PATH.exists() and cfg.ONSITE_DATA_PATH.exists() and (OUT_DIR / "forecasts.json").exists()),
    reason="model, onsite data or exported forecast cache not present",
)
ASOF = "2025-06-30"
CACHE = OUT_DIR / "forecasts.json"


@pytest.fixture(scope="module")
def weekly():
    return load_weekly(cfg.ONSITE_DATA_PATH)


@pytest.fixture(scope="module")
def model(weekly):
    bundle = load_bundle()
    return build_features(weekly, bundle["feature_params"]), bundle


def broken_model():
    raise ForecastError("model file not found: models/model.joblib")


def test_uses_the_model_when_it_loads(model, weekly):
    result = resilient_window(ASOF, 4, load_model=lambda: model, cache_path=CACHE, weekly=weekly)
    assert result.source == "model"
    pd.testing.assert_frame_equal(result.window, forecast_window(*model, ASOF, 4))


def test_falls_back_to_the_cached_forecast_when_the_model_is_missing(model, weekly):
    result = resilient_window(ASOF, 4, load_model=broken_model, cache_path=CACHE, weekly=weekly)
    assert result.source == "cache"
    assert "model file not found" in result.reason
    expected = forecast_window(*model, ASOF, 4)
    assert list(result.window.columns) == list(WINDOW_COLS)
    # The cache was exported on another machine: last-bit BLAS differences are allowed.
    np.testing.assert_allclose(result.window["expected_cases"], expected["expected_cases"], rtol=1e-9)
    assert (result.window["tier"] == expected["tier"]).all()


def test_falls_back_to_the_seasonal_baseline_without_model_or_cache(weekly, tmp_path):
    result = resilient_window(ASOF, 2, load_model=broken_model, cache_path=tmp_path / "none.json", weekly=weekly)
    assert result.source == "seasonal"
    assert list(result.window.columns) == list(WINDOW_COLS)
    assert len(result.window) == 60 * 2


def test_cache_without_the_requested_week_also_falls_through(weekly):
    result = resilient_window("2019-07-01", 2, load_model=broken_model, cache_path=CACHE, weekly=weekly)
    assert result.source == "seasonal"


def test_a_bad_asof_week_is_an_error_not_a_fallback(model, weekly):
    with pytest.raises(ForecastError, match="as-of"):
        resilient_window("2025-06-29", 2, load_model=lambda: model, cache_path=CACHE, weekly=weekly)


def test_seasonal_mean_is_the_same_iso_week_in_earlier_years(weekly):
    window = seasonal_window(weekly, ASOF, 1)
    target = pd.Timestamp(ASOF) + pd.Timedelta(weeks=1)
    ward = weekly[(weekly[cfg.WARD_COL] == "DNCC_Ward_05") & (weekly[cfg.DATE_COL] <= ASOF)]
    same_week = ward[ward[cfg.DATE_COL].dt.isocalendar().week == target.isocalendar().week]
    row = window[window[cfg.WARD_COL] == "DNCC_Ward_05"].iloc[0]
    assert row["expected_cases"] == pytest.approx(same_week[cfg.TARGET_COL].mean())
    assert row["p10_cases"] <= row["expected_cases"] <= row["p90_cases"]
    assert row["top_driver"] == "season"


def test_seasonal_baseline_never_sees_data_after_the_asof_week(weekly):
    after = weekly[cfg.DATE_COL] > ASOF
    tampered = weekly.assign(**{cfg.TARGET_COL: weekly[cfg.TARGET_COL].where(~after, 99)})
    pd.testing.assert_frame_equal(
        seasonal_window(tampered, ASOF, 4).drop(columns="actual_cases"),
        seasonal_window(weekly, ASOF, 4).drop(columns="actual_cases"),
    )
