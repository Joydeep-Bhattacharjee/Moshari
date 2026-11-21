import math
import warnings

import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.validate import DataValidationError, main, quality_report, validate


def make_df(n_wards: int = 2, n_weeks: int = cfg.MIN_WEEKS_PER_WARD) -> pd.DataFrame:
    dates = pd.date_range("2020-01-06", periods=n_weeks, freq=cfg.DATA_FREQ)
    rows = [
        {
            cfg.DATE_COL: day.strftime("%Y-%m-%d"),
            cfg.CITY_COL: "Dhaka North",
            cfg.WARD_COL: f"W{ward:02d}",
            cfg.DENSITY_COL: 40000 + ward,
            cfg.WATERLOG_COL: 0.5,
            cfg.SANITATION_COL: 0.6 - 0.1 * ward,
            cfg.TEMP_COL: 28.0,
            cfg.TEMP_MAX_COL: 32.0,
            cfg.TEMP_MIN_COL: 24.0,
            cfg.RAIN_COL: 10.0 * week,
            cfg.HUMIDITY_COL: 70.0,
            cfg.TARGET_COL: week + ward,
        }
        for ward in range(n_wards)
        for week, day in enumerate(dates)
    ]
    return pd.DataFrame(rows)


def with_value(df: pd.DataFrame, col: str, value) -> pd.DataFrame:
    bad = df.astype({col: object})
    bad.loc[0, col] = value
    return bad


def test_valid_data_passes():
    validate(make_df())


def test_validate_does_not_modify_input():
    df = make_df()
    snapshot = df.copy()
    validate(df)
    pd.testing.assert_frame_equal(df, snapshot)


def test_missing_column_is_reported_by_name():
    df = make_df().drop(columns=[cfg.RAIN_COL])
    with pytest.raises(DataValidationError, match=cfg.RAIN_COL):
        validate(df)


@pytest.mark.parametrize(
    ("col", "value", "message"),
    [
        (cfg.RAIN_COL, -1.0, cfg.RAIN_COL),
        (cfg.HUMIDITY_COL, 101.0, cfg.HUMIDITY_COL),
        (cfg.HUMIDITY_COL, -0.5, cfg.HUMIDITY_COL),
        (cfg.TEMP_COL, 51.0, cfg.TEMP_COL),
        (cfg.TEMP_MIN_COL, -6.0, cfg.TEMP_MIN_COL),
        (cfg.TARGET_COL, -1, cfg.TARGET_COL),
        (cfg.TARGET_COL, 2.5, "non-integer"),
        (cfg.DENSITY_COL, 0, cfg.DENSITY_COL),
        (cfg.RAIN_COL, "heavy", "non-numeric"),
        (cfg.RAIN_COL, np.nan, "missing values"),
        (cfg.DATE_COL, "not-a-date", "do not parse"),
    ],
)
def test_bad_value_fails_loudly(col, value, message):
    with pytest.raises(DataValidationError, match=message):
        validate(with_value(make_df(), col, value))


def test_boundary_values_pass():
    df = with_value(make_df(), cfg.RAIN_COL, 0.0)
    df = with_value(df, cfg.HUMIDITY_COL, 100.0)
    validate(df)


def test_duplicate_ward_date_fails():
    df = make_df()
    duplicated = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="duplicate"):
        validate(duplicated)


def test_ward_with_too_few_weeks_fails():
    with pytest.raises(DataValidationError, match="< 12 weeks"):
        validate(make_df(n_weeks=cfg.MIN_WEEKS_PER_WARD - 1))


def test_all_errors_are_collected():
    df = with_value(make_df(), cfg.RAIN_COL, -1.0)
    df = with_value(df, cfg.HUMIDITY_COL, 150.0)
    with pytest.raises(DataValidationError) as excinfo:
        validate(df)
    assert len(excinfo.value.errors) == 2


def test_quality_report_facts():
    report = quality_report(make_df(n_wards=3, n_weeks=20))
    assert report["n_wards"] == 3
    assert report["rows_per_ward"] == (20, 20)
    assert report["gap_days"] == [7]
    assert all(report["static_per_ward"].values())


def test_quality_report_constant_column_gives_nan_without_warning():
    df = make_df(n_wards=3)  # water_logging_risk_index is constant across wards
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        report = quality_report(df)
    assert math.isnan(report["ward_spearman_vs_mean_cases"][cfg.WATERLOG_COL])


def test_quality_report_flags_non_static_ward_column():
    df = with_value(make_df(), cfg.SANITATION_COL, 0.99)
    assert quality_report(df)["static_per_ward"][cfg.SANITATION_COL] is False


def test_cli_returns_error_code_for_missing_file(tmp_path, capsys):
    assert main(["--path", str(tmp_path / "nope.csv")]) == 1
    assert "not found" in capsys.readouterr().err


def test_cli_returns_error_code_for_invalid_file(tmp_path, capsys):
    path = tmp_path / "bad.csv"
    with_value(make_df(), cfg.RAIN_COL, -5.0).to_csv(path, index=False)
    assert main(["--path", str(path)]) == 1
    assert cfg.RAIN_COL in capsys.readouterr().err


@pytest.mark.skipif(not cfg.RAW_DATA_PATH.exists(), reason="raw data not present")
def test_real_dataset_passes_contract():
    df = pd.read_csv(cfg.RAW_DATA_PATH)
    validate(df)
    report = quality_report(df)
    assert report["n_wards"] == 60
    assert report["gap_days"] == [7]
    assert all(report["static_per_ward"].values())
