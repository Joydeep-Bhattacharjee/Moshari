"""Spray-crew need and priority-order assignment (PRD 6.1 crew rule)."""
import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.ops.crews import assign_crews, crews_needed
from src.ops.wards import ward_attributes


@pytest.mark.parametrize(
    ("risk", "waterlog", "crews"),
    [(0, 0.50, 0), (1, 0.74, 1), (2, 0.75, 3), (3, 0.94, 4), (0, 0.80, 1)],
)
def test_crews_needed_by_tier_plus_one_for_bad_drainage(risk, waterlog, crews):
    assert crews_needed(np.array([risk]), np.array([waterlog]))[0] == crews


def test_crews_go_in_priority_order_until_they_run_out():
    assert assign_crews(np.array([4, 3, 2]), 5).tolist() == [4, 1, 0]
    assert assign_crews(np.array([4, 3, 2]), 0).tolist() == [0, 0, 0]
    assert assign_crews(np.array([4, 3, 2]), 50).tolist() == [4, 3, 2]


def test_negative_crew_total_is_rejected():
    with pytest.raises(ValueError, match="crews"):
        assign_crews(np.array([1]), -1)


def _weekly(waterlog_by_week) -> pd.DataFrame:
    return pd.DataFrame(
        {
            cfg.WARD_COL: "W1",
            cfg.CITY_COL: "Gazipur",
            cfg.DATE_COL: pd.date_range("2020-01-06", periods=len(waterlog_by_week), freq="W-MON"),
            cfg.DENSITY_COL: 40000,
            cfg.WATERLOG_COL: waterlog_by_week,
            cfg.SANITATION_COL: 0.5,
        }
    )


def test_ward_attributes_one_row_per_ward():
    wards = ward_attributes(pd.concat([_weekly([0.8, 0.8]), _weekly([0.8]).assign(ward_id="W0")]))
    assert wards[cfg.WARD_COL].tolist() == ["W0", "W1"]
    assert list(wards.columns) == [cfg.WARD_COL, cfg.CITY_COL, *cfg.STATIC_WARD_COLS]


def test_ward_attributes_reject_values_that_change_over_time():
    with pytest.raises(ValueError, match=cfg.WATERLOG_COL):
        ward_attributes(_weekly([0.8, 0.7]))
