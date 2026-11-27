"""Constrained resource allocation (PRD 6.1): floors, priority greedy, alerts, LP optimality."""
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.optimize import linprog

from src import config as cfg
from src.ops.allocate import (
    ALLOCATION_COLS,
    alert_levels,
    allocate,
    allocate_units,
    equity_floors,
    greedy_fill,
    priority_scores,
    region_summary,
    stock_units,
)

DENSITY_REF = 74_252  # densest ward in the dataset


def prd_demand() -> pd.DataFrame:
    """PRD 6.1 worked example: real rows, Dhaka North, week 2025-06-30."""
    return pd.DataFrame(
        {
            cfg.WARD_COL: ["DNCC_Ward_05", "DNCC_Ward_12", "DNCC_Ward_13", "DNCC_Ward_16"],
            cfg.CITY_COL: "Dhaka North",
            "cases": [14, 23, 10, 2],
            cfg.SALINE_COL: [33, 55, 24, 5],
            cfg.KITS_COL: [16, 27, 12, 2],
            cfg.BEDS_COL: [4, 7, 3, 1],
            "risk_rank": [3, 3, 2, 0],
            cfg.DENSITY_COL: [65449, 72086, 35362, 55763],
        }
    )


def saline_rows(table: pd.DataFrame) -> pd.DataFrame:
    return table[table["resource"] == cfg.SALINE_COL].set_index(cfg.WARD_COL)


def test_prd_priority_values():
    scores = priority_scores(prd_demand(), DENSITY_REF).set_index(cfg.WARD_COL)
    assert scores["priority"].round(3).to_dict() == {
        "DNCC_Ward_05": 0.886,
        "DNCC_Ward_12": 0.991,
        "DNCC_Ward_13": 0.605,
        "DNCC_Ward_16": 0.368,
    }
    assert scores["priority_rank"].to_dict() == {
        "DNCC_Ward_12": 1,
        "DNCC_Ward_05": 2,
        "DNCC_Ward_13": 3,
        "DNCC_Ward_16": 4,
    }


def test_prd_worked_example_saline_at_60_percent_stock():
    rows = saline_rows(allocate(prd_demand(), 60, 15, DENSITY_REF))
    order = ["DNCC_Ward_12", "DNCC_Ward_05", "DNCC_Ward_13", "DNCC_Ward_16"]
    assert rows.loc[order, "need"].tolist() == [55, 33, 24, 5]
    assert rows.loc[order, "floor"].tolist() == [9, 5, 4, 1]
    assert rows.loc[order, "allocated"].tolist() == [55, 10, 4, 1]
    assert rows.loc[order, "alert"].tolist() == ["OK", "CRITICAL", "CRITICAL", "CRITICAL"]
    assert rows["allocated"].sum() == 70


def test_full_stock_fills_every_ward_with_no_alerts():
    table = allocate(prd_demand(), 100, 15, DENSITY_REF)
    assert list(table.columns) == list(ALLOCATION_COLS)
    assert (table["fill"] == 1.0).all()
    assert (table["alert"] == "OK").all()
    assert (table["deficit"] == 0).all()


def test_stock_is_floor_of_percent_of_need():
    assert stock_units(117, 60) == 70
    assert stock_units(0, 30) == 0
    assert stock_units(101, 30) == 30


@pytest.mark.parametrize("pct", [29, 101, 50.5])
def test_stock_percent_outside_30_to_100_is_rejected(pct):
    with pytest.raises(ValueError, match="stock_pct"):
        stock_units(100, pct)


@pytest.mark.parametrize("pct", [-1, 101])
def test_floor_percent_outside_0_to_100_is_rejected(pct):
    with pytest.raises(ValueError, match="floor_pct"):
        equity_floors(np.array([10]), pct)


def test_equity_floor_rounds_up():
    assert equity_floors(np.array([55, 33, 24, 5, 0]), 15).tolist() == [9, 5, 4, 1, 0]


def test_floors_that_do_not_fit_are_scaled_down_evenly():
    floors, alloc = allocate_units(np.array([10, 10, 10]), 7, 50)
    assert floors.tolist() == [3, 2, 2]  # Webster: highest-priority ward gets the odd unit
    assert alloc.tolist() == [3, 2, 2]


def test_alabama_paradox_case_stays_monotone():
    # Largest remainder on floors (1, 3, 3): stock 3 -> [1, 1, 1], stock 4 -> [0, 2, 2],
    # so ward 1 would lose units when stock grows. Webster-sequential cannot do that.
    _, at_3 = allocate_units(np.array([1, 3, 3]), 3, 100)
    _, at_4 = allocate_units(np.array([1, 3, 3]), 4, 100)
    assert at_3.tolist() == [1, 1, 1]
    assert at_4.tolist() == [1, 2, 1]


def test_greedy_fill_tops_up_in_order():
    assert greedy_fill(np.array([46, 28, 20, 4]), 51).tolist() == [46, 5, 0, 0]
    assert greedy_fill(np.array([3, 3]), 0).tolist() == [0, 0]


@pytest.mark.parametrize(
    ("fill", "risk", "alert"),
    [
        (1.0, 3, "OK"),
        (0.99, 0, "WARNING"),
        (0.8, 2, "WARNING"),
        (0.79, 2, "CRITICAL"),
        (0.79, 1, "WARNING"),
        (0.49, 0, "CRITICAL"),
    ],
)
def test_alert_rules(fill, risk, alert):
    assert alert_levels(np.array([fill]), np.array([risk]))[0] == alert


def test_ward_with_no_need_is_fully_supplied():
    demand = prd_demand().assign(**{cfg.SALINE_COL: [0, 55, 24, 5]})
    row = saline_rows(allocate(demand, 30, 15, DENSITY_REF)).loc["DNCC_Ward_05"]
    assert (row["need"], row["allocated"], row["fill"], row["alert"]) == (0, 0, 1.0, "OK")


def test_off_season_with_no_cases_does_not_divide_by_zero():
    demand = prd_demand().assign(cases=0, **{c: 0 for c in cfg.SUPPLY_COLS}, risk_rank=0)
    table = allocate(demand, 30, 15, DENSITY_REF)
    assert (table["alert"] == "OK").all()
    assert priority_scores(demand, DENSITY_REF)["cases_norm"].eq(0).all()


def test_equal_priority_ties_go_to_the_lower_ward_id():
    demand = pd.DataFrame(
        {
            cfg.WARD_COL: ["W_B", "W_A"],
            cfg.CITY_COL: "Gazipur",
            "cases": [5, 5],
            cfg.SALINE_COL: [10, 10],
            cfg.KITS_COL: [4, 4],
            cfg.BEDS_COL: [1, 1],
            "risk_rank": [1, 1],
            cfg.DENSITY_COL: [40000, 40000],
        }
    )
    rows = saline_rows(allocate(demand, 55, 0, DENSITY_REF))
    assert rows.loc["W_A", "allocated"] == 10
    assert rows.loc["W_B", "allocated"] == 1


def test_region_summary_reports_shortfalls():
    summary = region_summary(allocate(prd_demand(), 60, 15, DENSITY_REF))
    assert summary["critical_wards"] == 3
    assert summary["resources"][cfg.SALINE_COL] == {"need": 117, "allocated": 70, "short": 47}
    assert summary["banner"].startswith("3 wards critical · saline short 47 bags · kits short ")


def test_input_is_not_modified():
    demand = prd_demand()
    snapshot = demand.copy()
    allocate(demand, 60, 15, DENSITY_REF)
    pd.testing.assert_frame_equal(demand, snapshot)


def test_missing_column_is_rejected_by_name():
    with pytest.raises(ValueError, match=cfg.DENSITY_COL):
        allocate(prd_demand().drop(columns=[cfg.DENSITY_COL]), 60)


# --- Property tests (PRD 6.1 acceptance) -------------------------------------

needs = st.lists(st.integers(0, 80), min_size=1, max_size=12).map(np.array)
floor_pcts = st.integers(0, 100)


@settings(max_examples=200, deadline=None)
@given(needs, st.floats(0, 1), floor_pcts)
def test_allocation_uses_the_stock_and_respects_bounds(need, share, floor_pct):
    stock = int(share * need.sum())
    floors, alloc = allocate_units(need, stock, floor_pct)
    assert alloc.sum() == stock
    assert (alloc >= 0).all() and (alloc <= need).all()
    assert (floors <= alloc).all()
    if equity_floors(need, floor_pct).sum() <= stock:
        assert (floors == equity_floors(need, floor_pct)).all()


@settings(max_examples=200, deadline=None)
@given(needs, st.floats(0, 1), st.floats(0, 1), floor_pcts)
def test_less_stock_never_gives_any_ward_more(need, a, b, floor_pct):
    low, high = sorted((int(a * need.sum()), int(b * need.sum())))
    _, alloc_low = allocate_units(need, low, floor_pct)
    _, alloc_high = allocate_units(need, high, floor_pct)
    assert (alloc_low <= alloc_high).all()


@settings(max_examples=150, deadline=None)
@given(
    st.lists(st.tuples(st.integers(0, 80), st.floats(0, 1)), min_size=1, max_size=12),
    st.floats(0, 1),
    floor_pcts,
)
def test_greedy_matches_the_highs_lp_optimum(wards, share, floor_pct):
    ranked = sorted(wards, key=lambda w: -w[1])
    need = np.array([w[0] for w in ranked])
    priority = np.array([w[1] for w in ranked])
    stock = int(share * need.sum())
    floors, alloc = allocate_units(need, stock, floor_pct)
    capacity = need - floors
    lp = linprog(
        -priority,
        A_ub=np.ones((1, len(need))),
        b_ub=[stock - floors.sum()],
        bounds=list(zip(np.zeros(len(need)), capacity)),
        method="highs",
    )
    assert lp.status == 0
    greedy_objective = float(priority @ (alloc - floors))
    assert greedy_objective == pytest.approx(-lp.fun, abs=1e-7)
