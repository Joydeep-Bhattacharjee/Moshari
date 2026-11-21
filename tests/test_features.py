import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.data import load_weekly
from src.features import (
    FEATURE_COLS,
    FEATURE_GROUPS,
    TARGET_COLS,
    build_features,
    fit_feature_params,
    target_col,
)

RAIN_W0 = 10.0 * np.arange(20)  # matches conftest: ward W0 rain = 0, 10, 20, ...


def _build(weekly: pd.DataFrame) -> pd.DataFrame:
    return build_features(weekly, fit_feature_params(weekly, weekly[cfg.DATE_COL].max()))


def _ward(features: pd.DataFrame, ward: str) -> pd.DataFrame:
    return features[features[cfg.WARD_COL] == ward].reset_index(drop=True)


def test_rain_lags_match_manual_shift(weekly):
    w0 = _ward(_build(weekly), "W0")
    assert w0["rain_lag_0"].tolist() == RAIN_W0.tolist()
    assert w0.loc[5, "rain_lag_3"] == RAIN_W0[2]
    assert w0.loc[10, "rain_lag_8"] == RAIN_W0[2]


def test_no_cross_ward_leakage(weekly):
    w1 = _ward(_build(weekly), "W1")
    for k in range(1, 9):
        assert w1[f"rain_lag_{k}"].iloc[:k].isna().all(), f"rain_lag_{k} leaked from ward W0"
    assert w1.loc[1, "rain_lag_1"] == 1000.0


def test_targets_are_future_cases_of_same_ward(weekly):
    w0 = _ward(_build(weekly), "W0")
    for h in cfg.HORIZONS:
        assert w0.loc[3, target_col(h)] == 3 + h
        assert w0[target_col(h)].iloc[-h:].isna().all()


def test_no_target_columns_in_features():
    assert not [c for c in FEATURE_COLS if c.startswith("y_") or c == cfg.TARGET_COL]
    assert not set(TARGET_COLS) & set(FEATURE_COLS)


def test_feature_groups_cover_each_feature_once(weekly):
    grouped = [c for cols in FEATURE_GROUPS.values() for c in cols]
    assert len(grouped) == len(set(grouped)) == len(FEATURE_COLS)
    assert set(FEATURE_COLS) <= set(_build(weekly).columns)


def test_future_weather_does_not_change_past_features(weekly):
    cutoff = weekly[cfg.DATE_COL].iloc[10]
    later = weekly[cfg.DATE_COL] >= cutoff
    weather = [cfg.RAIN_COL, cfg.TEMP_COL, cfg.HUMIDITY_COL]
    changed = weekly.assign(**{col: weekly[col].where(~later, 999.0) for col in weather})
    params = fit_feature_params(weekly, weekly[cfg.DATE_COL].iloc[9])
    before, after = build_features(weekly, params), build_features(changed, params)
    past = before[cfg.DATE_COL] < cutoff
    pd.testing.assert_frame_equal(
        before.loc[past, list(FEATURE_COLS)], after.loc[past, list(FEATURE_COLS)]
    )


def test_heavy_rain_threshold_uses_training_weeks_only(weekly):
    train_end = weekly[cfg.DATE_COL].iloc[9]
    later = weekly[cfg.DATE_COL] > train_end
    changed = weekly.assign(**{cfg.RAIN_COL: weekly[cfg.RAIN_COL].where(~later, 1e6)})
    assert fit_feature_params(weekly, train_end) == fit_feature_params(changed, train_end)


def test_heavy_rain_weeks_counts_last_four_weeks_above_threshold(weekly):
    params = {"train_end": "2020-01-06", "heavy_rain_mm": {"W0": 105.0, "W1": 1e9}}
    w0 = _ward(build_features(weekly, params), "W0")
    assert w0.loc[12, "heavy_rain_weeks_4"] == 2  # weeks 9..12 have rain 90, 100, 110, 120
    assert np.isnan(w0.loc[2, "heavy_rain_weeks_4"])  # incomplete window


def test_rolling_rain_windows(weekly):
    w0 = _ward(_build(weekly), "W0")
    assert w0.loc[5, "rain_roll_4"] == 20 + 30 + 40 + 50
    assert w0.loc[5, "rain_sum_lag2_4"] == 30 + 20 + 10
    assert w0.loc[5, "rain_max_4"] == 50
    assert np.isnan(w0.loc[2, "rain_roll_4"])


def test_temp_suitable_counts_weeks_between_25_and_32(weekly):
    w0 = _ward(_build(weekly), "W0")
    assert w0.loc[5, "temp_suitable_4"] == 3  # temps 24, 25, 26, 27
    assert w0.loc[12, "temp_suitable_4"] == 2  # temps 31, 32, 33, 22


def test_interactions_use_ward_vulnerability(weekly):
    f = _build(weekly)
    rain = f["rain_sum_lag2_4"]
    assert np.allclose(f["rain2_4_x_waterlog"], rain * f[cfg.WATERLOG_COL], equal_nan=True)
    assert np.allclose(
        f["rain2_4_x_poor_sanitation"], rain * (1 - f[cfg.SANITATION_COL]), equal_nan=True
    )


def test_season_encoding_on_unit_circle(weekly):
    f = _build(weekly)
    assert np.allclose(f["week_sin"] ** 2 + f["week_cos"] ** 2, 1.0)


def test_build_features_sorts_and_does_not_modify_input(weekly):
    shuffled = weekly.sample(frac=1, random_state=0)
    snapshot = shuffled.copy()
    params = fit_feature_params(weekly, weekly[cfg.DATE_COL].max())
    result = build_features(shuffled, params)
    pd.testing.assert_frame_equal(shuffled, snapshot)
    pd.testing.assert_frame_equal(result, build_features(weekly, params))


def test_unknown_ward_in_params_raises(weekly):
    params = {"train_end": "2020-01-06", "heavy_rain_mm": {"W0": 1.0}}
    with pytest.raises(ValueError, match="W1"):
        build_features(weekly, params)


def test_fit_params_without_training_weeks_raises(weekly):
    with pytest.raises(ValueError, match="no training weeks"):
        fit_feature_params(weekly, "2000-01-03")


@pytest.mark.skipif(not cfg.RAW_DATA_PATH.exists(), reason="raw data not present")
def test_real_features_complete_after_warmup():
    weekly = load_weekly()
    features = _build(weekly)
    week_index = features.groupby(cfg.WARD_COL).cumcount()
    warm = features[week_index >= 8]  # longest lag is 8 weeks
    assert not warm[list(FEATURE_COLS)].isna().any().any()
    assert len(features) == len(weekly)
