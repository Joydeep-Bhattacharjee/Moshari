"""Ward demand over a forecast window (PRD 6.1 demand block)."""
import pandas as pd
import pytest

from src import config as cfg
from src.ops.demand import DEMAND_COLS, ward_demand


def make_window(rows) -> pd.DataFrame:
    """rows: (ward, week_ahead, expected_cases, p90_cases, tier_rank)."""
    return pd.DataFrame(
        [
            {
                cfg.WARD_COL: ward,
                cfg.CITY_COL: "Dhaka North",
                "week_ahead": week,
                "expected_cases": expected,
                "p90_cases": p90,
                "tier_rank": tier,
            }
            for ward, week, expected, p90, tier in rows
        ]
    )


def test_prd_worked_example_needs_117_bags():
    window = make_window(
        [
            ("DNCC_Ward_12", 1, 23, 30, 3),
            ("DNCC_Ward_05", 1, 14, 20, 3),
            ("DNCC_Ward_13", 1, 10, 15, 2),
            ("DNCC_Ward_16", 1, 2, 4, 0),
        ]
    )
    demand = ward_demand(window).set_index(cfg.WARD_COL)
    assert demand[cfg.SALINE_COL].to_dict() == {
        "DNCC_Ward_05": 33,
        "DNCC_Ward_12": 55,
        "DNCC_Ward_13": 24,
        "DNCC_Ward_16": 5,
    }
    assert demand[cfg.SALINE_COL].sum() == 117
    assert demand.loc["DNCC_Ward_05", cfg.KITS_COL] == 16
    assert demand.loc["DNCC_Ward_05", cfg.BEDS_COL] == 4


def test_saline_and_kits_add_up_weeks_beds_take_the_peak_week():
    demand = ward_demand(make_window([("W1", 1, 4, 5, 0), ("W1", 2, 10, 12, 2)])).iloc[0]
    assert demand[cfg.SALINE_COL] == 10 + 24  # 9.54 -> 10, 23.85 -> 24
    assert demand[cfg.KITS_COL] == 5 + 12  # 4.66 -> 5, 11.65 -> 12
    assert demand[cfg.BEDS_COL] == 3  # max(1.2 -> 1, 3.0 -> 3); beds are reused, not consumed
    assert demand["cases"] == 14
    assert demand["peak_weekly_cases"] == 10
    assert demand["window_weeks"] == 2


def test_each_week_is_rounded_before_summing():
    # 0.2 cases -> 0.477 bags -> 0 each week; rounding the 2-week sum would give 1
    demand = ward_demand(make_window([("W1", 1, 0.2, 0.3, 0), ("W1", 2, 0.2, 0.3, 0)])).iloc[0]
    assert demand[cfg.SALINE_COL] == 0


def test_bad_case_plans_on_p90():
    window = make_window([("W1", 1, 4, 10, 0)])
    assert ward_demand(window, "likely").iloc[0][cfg.SALINE_COL] == 10
    bad = ward_demand(window, "bad").iloc[0]
    assert bad[cfg.SALINE_COL] == 24
    assert bad["confidence"] == "bad"
    assert bad["cases"] == 10


def test_risk_is_the_highest_weekly_tier_in_the_window():
    demand = ward_demand(make_window([("W1", 1, 4, 5, 0), ("W1", 2, 10, 12, 2)])).iloc[0]
    assert demand["risk_rank"] == 2
    assert demand["risk"] == "High"


def test_one_row_per_ward_sorted_by_ward():
    window = make_window([("W2", 1, 1, 2, 0), ("W1", 1, 1, 2, 0), ("W2", 2, 1, 2, 0)])
    demand = ward_demand(window)
    assert list(demand.columns) == list(DEMAND_COLS)
    assert demand[cfg.WARD_COL].tolist() == ["W1", "W2"]


def test_supply_columns_are_integers():
    demand = ward_demand(make_window([("W1", 1, 3.7, 6.1, 1)]))
    assert all(pd.api.types.is_integer_dtype(demand[c]) for c in cfg.SUPPLY_COLS)


def test_input_is_not_modified():
    window = make_window([("W1", 1, 4, 5, 0)])
    snapshot = window.copy()
    ward_demand(window)
    pd.testing.assert_frame_equal(window, snapshot)


def test_unknown_confidence_is_rejected():
    with pytest.raises(ValueError, match="confidence"):
        ward_demand(make_window([("W1", 1, 4, 5, 0)]), "worst")


def test_missing_column_is_rejected_by_name():
    window = make_window([("W1", 1, 4, 5, 0)]).drop(columns=["p90_cases"])
    with pytest.raises(ValueError, match="p90_cases"):
        ward_demand(window)


def test_empty_window_is_rejected():
    empty = make_window([("W1", 1, 4, 5, 0)]).iloc[0:0]
    with pytest.raises(ValueError, match="empty"):
        ward_demand(empty)
