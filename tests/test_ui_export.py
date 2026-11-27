"""Phase 2 UI data export (public/data/ops): constants, wards, cached forecast windows."""
import json
import math

import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.ops import allocate, simulate
from src.ops.forecast_window import forecast_window
from src.ops.pipeline import load_context
from src.ops.ui_export import FIRST_ASOF, build_config, build_forecasts, closed_form_ratio

pytestmark = pytest.mark.skipif(
    not (cfg.MODEL_PATH.exists() and cfg.ONSITE_DATA_PATH.exists()),
    reason="trained model or onsite data not present",
)
ASOF = "2025-06-30"


@pytest.fixture(scope="module")
def ctx():
    return load_context(git_commit="test")


@pytest.fixture(scope="module")
def config(ctx):
    return build_config(ctx)


@pytest.fixture(scope="module")
def forecasts(ctx):
    return build_forecasts(ctx)


def test_constants_are_read_from_the_python_modules(config):
    constants = config["constants"]
    assert constants["bands"] == simulate.BANDS
    assert constants["risk_norm"] == list(allocate.RISK_NORM)
    assert constants["supply_per_1000"] == cfg.SUPPLY_PER_1000_CASES
    assert constants["waterlog_floor"] == simulate.WATERLOG_FLOOR
    assert constants["ramp_by_week"] == {str(k): v for k, v in simulate.RAMP_BY_WEEK.items()}


def test_wards_carry_static_attributes_and_capacity(config, ctx):
    wards = config["wards"]
    assert [w["id"] for w in wards] == sorted(ctx.wards[cfg.WARD_COL])
    assert all(1 <= w["capacity"] <= 5 for w in wards)
    assert config["provenance"]["data_hash"] == ctx.data_hash


def test_forecast_cache_covers_every_asof_week_with_four_weeks(forecasts):
    weeks = forecasts["asof_weeks"]
    assert weeks[0] == FIRST_ASOF and weeks[-1] == "2025-12-29"
    assert len(weeks) == len(set(weeks)) == len(forecasts["windows"])
    ward = forecasts["windows"][ASOF]["DNCC_Ward_05"]
    assert all(len(ward[key]) == 4 for key in ("expected", "p10", "p90", "tier_rank", "actual", "top_driver"))


def test_cached_window_is_the_python_forecast_at_full_precision(forecasts, ctx):
    window = forecast_window(ctx.frame, ctx.bundle, ASOF, 4)
    for ward, rows in window.groupby(cfg.WARD_COL):
        cached = forecasts["windows"][ASOF][ward]
        assert cached["expected"] == rows["expected_cases"].tolist()
        assert cached["p90"] == rows["p90_cases"].tolist()
        assert cached["tier_rank"] == rows["tier_rank"].tolist()


def test_files_are_valid_json_without_nan(config, forecasts):
    json.dumps(config, allow_nan=False)
    json.dumps(forecasts, allow_nan=False)
    assert forecasts["windows"]["2025-12-29"]["DNCC_Ward_05"]["actual"] == [None, None, None, None]


def test_closed_form_crew_effect_equals_re_running_the_model(forecasts, ctx):
    """The browser uses exp(-(b_wl + b_int * rain) * d_wl); Python re-runs the GLM."""
    window = forecast_window(ctx.frame, ctx.bundle, ASOF, 4)
    coef = simulate.drainage_coefficients(ctx.bundle)
    wl = ctx.wards.set_index(cfg.WARD_COL)[cfg.WATERLOG_COL]
    for crews in range(1, simulate.MAX_CREWS_PER_WARD + 1):
        sim = simulate.simulate(ctx.frame, ctx.bundle, window, pd.Series(crews, index=wl.index), "high")
        for row in sim[sim["week_ahead"] > 1].itertuples():
            horizon = simulate.EFFECT_HORIZON_BY_WEEK[row.week_ahead]
            rain = forecasts["windows"][ASOF][row.ward_id]["rain_sum"]
            expected = closed_form_ratio(coef[horizon], rain, wl[row.ward_id], row.waterlog_after)
            assert math.isclose(row.effect_ratio, expected, rel_tol=1e-12), row.ward_id


def test_closed_form_is_one_when_nothing_changes():
    assert closed_form_ratio({"waterlog": 0.8, "rain_x_waterlog": 0.0004}, 120.0, 0.7, 0.7) == 1.0
    assert np.isclose(closed_form_ratio({"waterlog": 1.0, "rain_x_waterlog": 0.0}, 0.0, 0.5, 0.4), math.exp(-0.1))
