"""Bed capacity proxy and same-city overflow routing (PRD 6.2)."""
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src import config as cfg
from src.ops.capacity import bed_capacity
from src.ops.overflow import (
    CITY_COLS,
    TRANSFER_COLS,
    WARD_ROUTE_COLS,
    max_flow_moved,
    route_overflow,
    usable_capacity,
)

TRAIN_END = "2024-05-27"


def city_table(rows, city="Gazipur") -> pd.DataFrame:
    """rows: (ward, required beds, capacity, priority)."""
    return pd.DataFrame(
        [
            {cfg.WARD_COL: w, cfg.CITY_COL: city, cfg.BEDS_COL: r, "capacity": c, "priority": p}
            for w, r, c, p in rows
        ]
    )


def test_deficit_ward_sends_patients_to_a_donor_with_headroom():
    result = route_overflow(city_table([("A", 7, 4, 0.9), ("B", 1, 5, 0.5), ("C", 2, 3, 0.4)]))
    assert list(result.transfers.columns) == list(TRANSFER_COLS)
    assert result.transfers[["from_ward", "to_ward", "patients"]].values.tolist() == [["A", "B", 3]]
    wards = result.wards.set_index(cfg.WARD_COL)
    assert list(result.wards.columns) == list(WARD_ROUTE_COLS)
    assert wards.loc["A", ["deficit_before", "sent", "unplaced"]].tolist() == [3, 3, 0]
    assert wards.loc["B", ["received", "headroom_after"]].tolist() == [3, 0]


def test_least_utilised_donor_is_used_first():
    result = route_overflow(city_table([("A", 6, 3, 0.9), ("B", 1, 5, 0.5), ("D", 0, 2, 0.1)]))
    assert result.transfers[["to_ward", "patients"]].values.tolist() == [["D", 1], ["B", 2]]


def test_higher_priority_deficit_ward_is_placed_first_when_beds_are_scarce():
    result = route_overflow(city_table([("A", 5, 3, 0.2), ("B", 5, 3, 0.9), ("C", 0, 3, 0.1)]))
    assert result.transfers[["from_ward", "patients"]].values.tolist() == [["B", 2]]
    assert result.wards.set_index(cfg.WARD_COL).loc["A", "unplaced"] == 2


def test_patients_never_cross_city_lines_and_saturation_is_flagged():
    table = pd.concat(
        [
            city_table([("G1", 6, 3, 0.9), ("G2", 3, 3, 0.5)], "Gazipur"),
            city_table([("N1", 0, 5, 0.1)], "Narayanganj"),
        ],
        ignore_index=True,
    )
    result = route_overflow(table)
    assert result.transfers.empty
    cities = result.cities.set_index(cfg.CITY_COL)
    assert list(result.cities.columns) == list(CITY_COLS)
    assert cities.loc["Gazipur", ["unplaced", "alert"]].tolist() == [3, "CITY_SATURATED"]
    assert cities.loc["Narayanganj", ["unplaced", "alert"]].tolist() == [0, "OK"]


def test_ten_percent_buffer_is_kept_free_on_donors():
    assert usable_capacity(pd.Series([1, 3, 5, 10])).tolist() == [0, 2, 4, 9]
    result = route_overflow(city_table([("A", 9, 1, 0.9), ("B", 0, 1, 0.5)]))
    assert result.transfers.empty  # 1 bed minus 10% buffer leaves no usable bed


def test_city_summary_reports_utilisation_and_cross_check():
    result = route_overflow(city_table([("A", 7, 4, 0.9), ("B", 1, 5, 0.5), ("C", 2, 3, 0.4)]))
    city = result.cities.iloc[0]
    assert (city["required"], city["capacity"], city["moved"], city["max_flow"]) == (10, 12, 3, 3)
    assert city["utilization_pct"] == pytest.approx(10 / 12 * 100)


def test_missing_column_is_rejected_by_name():
    with pytest.raises(ValueError, match="capacity"):
        route_overflow(city_table([("A", 1, 1, 0.1)]).drop(columns=["capacity"]))


def test_input_is_not_modified():
    table = city_table([("A", 7, 4, 0.9), ("B", 1, 5, 0.5)])
    snapshot = table.copy()
    route_overflow(table)
    pd.testing.assert_frame_equal(table, snapshot)


# --- Property tests (PRD 6.2 acceptance) -------------------------------------

ward_rows = st.lists(
    st.tuples(st.integers(0, 15), st.integers(1, 6), st.floats(0, 1)), min_size=1, max_size=10
)


def random_table(cities) -> pd.DataFrame:
    return pd.concat(
        [
            city_table([(f"C{i}_W{j:02d}", r, c, p) for j, (r, c, p) in enumerate(rows)], f"City{i}")
            for i, rows in enumerate(cities)
        ],
        ignore_index=True,
    )


@settings(max_examples=150, deadline=None)
@given(st.lists(ward_rows, min_size=1, max_size=3))
def test_routing_invariants(cities):
    table = random_table(cities)
    result = route_overflow(table)
    wards = result.wards.set_index(cfg.WARD_COL)
    city_of = table.set_index(cfg.WARD_COL)[cfg.CITY_COL]
    for _, t in result.transfers.iterrows():
        assert city_of[t["from_ward"]] == city_of[t["to_ward"]] == t[cfg.CITY_COL]
    for city, rows in result.wards.groupby(cfg.CITY_COL):
        assert rows["sent"].sum() == rows["received"].sum()
        summary = result.cities.set_index(cfg.CITY_COL).loc[city]
        assert summary["moved"] == summary["max_flow"]
        if rows["required"].sum() <= rows["usable"].sum():
            assert summary["unplaced"] == 0
    donors = wards[wards["received"] > 0]
    assert (donors["required"] + donors["received"] <= donors["usable"]).all()
    assert (wards["unplaced"] == wards["deficit_before"] - wards["sent"]).all()


@settings(max_examples=50, deadline=None)
@given(st.lists(ward_rows, min_size=1, max_size=3))
def test_routing_is_deterministic(cities):
    table = random_table(cities)
    first, second = route_overflow(table), route_overflow(table)
    pd.testing.assert_frame_equal(first.transfers, second.transfers)
    pd.testing.assert_frame_equal(first.wards, second.wards)


def test_max_flow_on_a_known_city():
    assert max_flow_moved([7, 1, 2], [4, 5, 3]) == 3
    assert max_flow_moved([9, 0], [1, 1]) == 0


# --- Capacity proxy -----------------------------------------------------------

def beds_history(beds, ward="W1", start="2024-04-29") -> pd.DataFrame:
    return pd.DataFrame(
        {
            cfg.WARD_COL: ward,
            cfg.DATE_COL: pd.date_range(start, periods=len(beds), freq="W-MON").strftime("%Y-%m-%d"),
            cfg.BEDS_COL: beds,
        }
    )


def test_capacity_is_p75_of_non_zero_training_weeks_as_an_observed_value():
    history = beds_history([0, 1, 2, 3, 4, 9])  # last week (9) is after TRAIN_END
    capacity = bed_capacity(history, TRAIN_END).iloc[0]
    assert capacity["capacity"] == 4  # P75 of [1, 2, 3, 4], 'higher' -> an observed count
    assert capacity["capacity_source"] == "proxy P75"


def test_ward_without_positive_training_history_is_rejected():
    with pytest.raises(ValueError, match="W1"):
        bed_capacity(beds_history([0, 0, 0]), TRAIN_END)


@pytest.mark.skipif(not cfg.ONSITE_DATA_PATH.exists(), reason="onsite data not present")
def test_capacity_on_the_onsite_data_is_1_to_5_beds_for_all_60_wards():
    capacity = bed_capacity(pd.read_csv(cfg.ONSITE_DATA_PATH), TRAIN_END)
    assert len(capacity) == 60
    assert capacity["capacity"].between(1, 5).all()
