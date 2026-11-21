import numpy as np
import pandas as pd
import pytest
import sklearn

from src import config as cfg
from src.data import load_weekly
from src.predict import (
    ForecastError,
    load_bundle,
    load_feature_frame,
    predict_all_wards,
    predict_one,
    valid_dates,
)
from src.report import main as report_main
from src.scenario import run_scenario, scale_recent_rain
from src.tiers import TIERS

pytestmark = pytest.mark.skipif(not cfg.MODEL_PATH.exists(), reason="trained model not present")

MONSOON = "2025-08-04"
DRY = "2025-12-29"
WARD = "DSCC_Ward_05"


@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


@pytest.fixture(scope="module")
def frame(bundle):
    return load_feature_frame(bundle)


@pytest.fixture(scope="module")
def weekly():
    return load_weekly()


def test_bundle_matches_installed_sklearn_and_has_all_parts(bundle):
    assert bundle["sklearn_version"] == sklearn.__version__
    for h in cfg.HORIZONS:
        assert set(bundle["models"][h]) == {"point", "q10", "q90"}
        assert len(bundle["thresholds"][h]) == 3


@pytest.mark.parametrize("horizon", cfg.HORIZONS)
def test_all_wards_ranked_with_valid_tiers_and_ordered_interval(frame, bundle, horizon):
    table = predict_all_wards(frame, bundle, MONSOON, horizon)
    assert len(table) == 60 and table[cfg.WARD_COL].is_unique
    assert set(table["tier"]) <= set(TIERS)
    assert (table["low_80"] >= 0).all()
    assert (table["low_80"] <= table["predicted_cases"] + 1e-9).all()
    assert (table["predicted_cases"] <= table["high_80"] + 1e-9).all()
    assert table["tier_rank"].is_monotonic_decreasing
    assert table["rank"].tolist() == list(range(1, 61))
    assert (table["target_week"] == table["forecast_week"] + pd.Timedelta(weeks=horizon)).all()


def test_different_inputs_give_different_outputs(frame, bundle):
    monsoon = predict_all_wards(frame, bundle, MONSOON, 3)
    dry = predict_all_wards(frame, bundle, DRY, 3)
    assert monsoon["predicted_cases"].mean() > dry["predicted_cases"].mean()
    assert monsoon["predicted_cases"].nunique() > 1


def test_actuals_known_in_past_and_missing_in_future(frame, bundle):
    assert predict_all_wards(frame, bundle, MONSOON, 3)["actual_cases"].notna().all()
    assert predict_all_wards(frame, bundle, DRY, 3)["actual_cases"].isna().all()


def test_predict_one_explains_itself(frame, bundle):
    result = predict_one(frame, bundle, WARD, MONSOON, 3)
    assert result["sentence"].startswith(f"{result['tier']} risk in 3 weeks")
    assert set(result["impacts"]) <= {"rain", "temperature", "humidity", "ward", "interactions", "season"}


@pytest.mark.parametrize(
    ("ward", "date", "horizon", "message"),
    [
        (WARD, MONSOON, 5, "horizon must be one of"),
        ("NOT_A_WARD", MONSOON, 3, "unknown ward"),
        (WARD, "2030-01-07", 3, "no data for week"),
        (WARD, "2016-01-11", 3, "too early"),
    ],
)
def test_bad_requests_raise_friendly_errors(frame, bundle, ward, date, horizon, message):
    with pytest.raises(ForecastError, match=message):
        predict_one(frame, bundle, ward, date, horizon)


def test_valid_dates_start_after_lag_warmup(frame):
    dates = valid_dates(frame)
    assert dates[0] == pd.Timestamp("2016-02-29")  # 8 weeks after the first week
    assert dates[-1] == pd.Timestamp("2025-12-29")


def test_scale_recent_rain_touches_only_last_four_weeks_of_one_ward(weekly):
    scaled = scale_recent_rain(weekly, WARD, MONSOON, 2.0)
    touched = weekly[scaled[cfg.RAIN_COL] != weekly[cfg.RAIN_COL]]
    window_start = pd.Timestamp(MONSOON) - pd.Timedelta(weeks=3)
    assert set(touched[cfg.WARD_COL]) == {WARD}
    assert touched[cfg.DATE_COL].between(window_start, pd.Timestamp(MONSOON)).all()


def test_scenario_multiplier_one_changes_nothing(weekly, bundle):
    result = run_scenario(weekly, bundle, WARD, MONSOON, 3, 1.0)
    assert result["change_cases"] == 0
    assert result["baseline"] == result["scenario"]


@pytest.mark.parametrize("horizon", [2, 3])
def test_more_rain_never_lowers_forecast_per_ward(weekly, bundle, horizon):
    for ward in sorted(weekly[cfg.WARD_COL].unique())[::6]:
        result = run_scenario(weekly, bundle, ward, MONSOON, horizon, 2.0)
        assert result["scenario"]["predicted_cases"] >= result["baseline"]["predicted_cases"] - 1e-9, ward


def test_more_rain_raises_citywide_forecast_at_four_weeks(weekly, bundle):
    # h=4 is only constrained on rain_sum_lag2_4, so single wards can dip slightly (see MODEL_CARD).
    wards = sorted(weekly[cfg.WARD_COL].unique())[::6]
    results = [run_scenario(weekly, bundle, w, MONSOON, 4, 2.0) for w in wards]
    assert sum(r["change_cases"] for r in results) > 0


def test_scenario_rejects_out_of_range_multiplier(weekly, bundle):
    with pytest.raises(ForecastError, match="between 0.5 and 2.0"):
        run_scenario(weekly, bundle, WARD, MONSOON, 3, 5.0)


def test_report_cli_writes_ranked_csv(tmp_path, capsys):
    assert report_main(["--date", MONSOON, "--horizon", "3", "--out", str(tmp_path)]) == 0
    report = pd.read_csv(tmp_path / f"spray_plan_{MONSOON}_h3.csv")
    assert len(report) == 60
    assert report["rank"].tolist() == list(range(1, 61))
    assert np.isfinite(report["predicted_cases"]).all()
    assert "wrote" in capsys.readouterr().out


def test_report_cli_rejects_bad_date(tmp_path, capsys):
    assert report_main(["--date", "2030-01-07", "--out", str(tmp_path)]) == 1
    assert "no data for week" in capsys.readouterr().err
