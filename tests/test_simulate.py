"""What-if vector-control simulator (PRD 6.3 acceptance)."""
import itertools

import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.data import load_weekly
from src.features import build_features
from src.ops.demand import ward_demand
from src.ops.forecast_window import forecast_window
from src.ops.simulate import (
    BANDS,
    MAX_CREWS_PER_WARD,
    SIM_COLS,
    auto_suggest,
    crew_reduction,
    drainage_coefficients,
    intervened_waterlog,
    intervened_window,
    prevented_table,
    roi_leaderboard,
    simulate,
)
from src.predict import load_bundle

ASOF = "2025-06-30"
needs_model = pytest.mark.skipif(
    not (cfg.MODEL_PATH.exists() and cfg.ONSITE_DATA_PATH.exists()),
    reason="trained model or onsite data not present",
)


# --- Pure formulas -------------------------------------------------------------

def test_crew_reduction_has_diminishing_returns():
    reduction = crew_reduction(np.arange(0, 7), "base")
    assert reduction[0] == 0
    assert np.all(np.diff(reduction) > 0)
    assert np.all(np.diff(reduction, 2) < 0)
    assert reduction[-1] < BANDS["base"]
    assert crew_reduction(np.array([2]), "base")[0] == pytest.approx(0.30 * (1 - np.exp(-1)))


def test_bands_scale_the_maximum_effect():
    one = {band: crew_reduction(np.array([1]), band)[0] for band in BANDS}
    assert one["low"] < one["base"] < one["high"]


@pytest.mark.parametrize(("crews", "band"), [(np.array([-1]), "base"), (np.array([7]), "base"), (np.array([1]), "max")])
def test_bad_crew_input_is_rejected(crews, band):
    with pytest.raises(ValueError):
        crew_reduction(crews, band)


def test_intervention_follows_the_ramp_and_never_goes_below_the_observed_minimum():
    wl = np.array([0.9, 0.9, 0.25])
    assert intervened_waterlog(wl, np.array([0.3, 0.3, 0.3]), 0.0).tolist() == [0.9, 0.9, 0.25]
    after = intervened_waterlog(wl, np.array([0.3, 0.3, 0.3]), 0.5)
    assert after[0] == pytest.approx(0.9 * (1 - 0.15))
    assert after[2] == 0.22  # clamped to the lowest index in the data
    assert intervened_waterlog(np.array([0.2]), np.array([0.3]), 1.0)[0] == 0.2  # never raised


# --- Model in the loop -----------------------------------------------------------

@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


@pytest.fixture(scope="module")
def frame(bundle):
    return build_features(load_weekly(cfg.ONSITE_DATA_PATH), bundle["feature_params"])


@pytest.fixture(scope="module")
def window(frame, bundle):
    return forecast_window(frame, bundle, ASOF, 4)


@pytest.fixture(scope="module")
def table(frame, bundle, window):
    return prevented_table(frame, bundle, window, "base")


@needs_model
def test_drainage_effect_is_monotone_by_construction(bundle):
    # log(cases) moves by (b_wl + b_int * recent_rain) * d_wl with both terms >= 0,
    # so lowering water-logging can only lower the forecast.
    for horizon, coef in drainage_coefficients(bundle).items():
        assert coef["waterlog"] > 0 and coef["rain_x_waterlog"] > 0, horizon


@needs_model
def test_zero_crews_reproduce_the_baseline_bit_for_bit(frame, bundle, window):
    sim = simulate(frame, bundle, window, pd.Series(dtype=int))
    assert list(sim.columns) == list(SIM_COLS)
    np.testing.assert_array_equal(sim["expected_after"].to_numpy(), sim["expected_cases"].to_numpy())
    np.testing.assert_array_equal(sim["p90_after"].to_numpy(), sim["p90_cases"].to_numpy())
    assert (sim["prevented"] == 0).all()


@needs_model
def test_week_one_is_unaffected_because_crews_need_time(frame, bundle, window):
    crews = pd.Series(3, index=window[cfg.WARD_COL].unique())
    sim = simulate(frame, bundle, window, crews)
    assert (sim.loc[sim["week_ahead"] == 1, "prevented"] == 0).all()
    lowered = sim["waterlog_after"] < sim["waterlog"]
    assert (sim.loc[(sim["week_ahead"] > 1) & lowered, "prevented"] > 0).all()
    # Wards already at the lowest index in the data (0.22) cannot be pushed lower: no effect.
    at_floor = sim[(sim["week_ahead"] > 1) & ~lowered]
    assert (at_floor["waterlog"] == 0.22).all()
    assert (at_floor["prevented"] == 0).all()


@needs_model
def test_prevented_cases_stay_between_zero_and_the_baseline(frame, bundle, window):
    sim = simulate(frame, bundle, window, pd.Series(MAX_CREWS_PER_WARD, index=window[cfg.WARD_COL].unique()))
    assert (sim["prevented"] >= 0).all()
    assert (sim["expected_after"] >= 0).all()
    assert (sim["prevented"] <= sim["expected_cases"]).all()
    assert (sim["p90_after"] >= sim["expected_after"]).all()


@needs_model
def test_more_crews_prevent_more_with_shrinking_marginal_gains(table):
    gains = np.diff(table.to_numpy(), axis=1)
    assert (gains >= -1e-12).all()
    assert (np.diff(gains, axis=1) <= 1e-9).all()


@needs_model
def test_longer_window_never_prevents_less(frame, bundle):
    crews = pd.Series(2, index=["DNCC_Ward_12", "DSCC_Ward_05"])
    totals = [
        simulate(frame, bundle, forecast_window(frame, bundle, ASOF, weeks), crews)["prevented"].sum()
        for weeks in (2, 3, 4)
    ]
    assert totals == sorted(totals)


@needs_model
def test_off_season_gives_near_zero_roi_without_errors(frame, bundle):
    quiet = forecast_window(frame, bundle, "2025-12-29", 4)
    board = roi_leaderboard(prevented_table(frame, bundle, quiet, "base"))
    assert board["prevented_per_crew"].max() < 0.5
    assert np.isfinite(board["prevented_per_crew"]).all()


@needs_model
def test_auto_suggest_matches_brute_force_on_a_small_case(table):
    small = table.loc[["DNCC_Ward_12", "DNCC_Ward_05", "GCC_Ward_03"]]
    plan = auto_suggest(small, 4)
    best = max(
        sum(small.iloc[i, c] for i, c in enumerate(combo))
        for combo in itertools.product(range(MAX_CREWS_PER_WARD + 1), repeat=3)
        if sum(combo) <= 4
    )
    assert plan.sum() <= 4
    assert sum(small.loc[w, c] for w, c in plan.items()) == pytest.approx(best)


@needs_model
def test_auto_suggest_respects_the_crew_total_and_per_ward_cap(table):
    plan = auto_suggest(table, 20)
    assert plan.sum() == 20
    assert plan.between(0, MAX_CREWS_PER_WARD).all()


@needs_model
def test_roi_leaderboard_ranks_by_cases_prevented_per_crew(table):
    board = roi_leaderboard(table)
    assert board["prevented_per_crew"].is_monotonic_decreasing
    assert board["rank"].tolist() == list(range(1, len(board) + 1))


@needs_model
def test_intervention_feeds_back_into_demand(frame, bundle, window):
    crews = pd.Series(4, index=window[cfg.WARD_COL].unique())
    after = intervened_window(simulate(frame, bundle, window, crews), bundle)
    before_demand, after_demand = ward_demand(window), ward_demand(after)
    assert (after_demand[cfg.SALINE_COL] <= before_demand[cfg.SALINE_COL]).all()
    assert after_demand[cfg.SALINE_COL].sum() < before_demand[cfg.SALINE_COL].sum()
    assert (after["tier_rank"] <= window["tier_rank"]).all()
