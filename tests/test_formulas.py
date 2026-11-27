"""Supply formulas reproduce the dataset's own columns (PRD 6.1 acceptance: 100% of rows)."""
from decimal import ROUND_HALF_DOWN, Decimal

import numpy as np
import pandas as pd
import pytest

from src import config as cfg
from src.ops.demand import supply_units


def _oracle(cases: int, per_1000: int) -> int:
    """Exact decimal product rounded half down: independent of the code under test."""
    exact = Decimal(per_1000) / 1000 * cases
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_DOWN))


@pytest.mark.parametrize("col", cfg.SUPPLY_COLS)
def test_matches_exact_decimal_rounding_for_every_count_up_to_10000(col):
    per_1000 = cfg.SUPPLY_PER_1000_CASES[col]
    cases = np.arange(0, 10_001)
    expected = np.array([_oracle(int(c), per_1000) for c in cases])
    np.testing.assert_array_equal(supply_units(cases, per_1000), expected)


@pytest.mark.skipif(not cfg.ONSITE_DATA_PATH.exists(), reason="onsite data not present")
@pytest.mark.parametrize("col", cfg.SUPPLY_COLS)
def test_reproduces_dataset_column_on_every_row(col):
    df = pd.read_csv(cfg.ONSITE_DATA_PATH, usecols=[cfg.TARGET_COL, col])
    got = supply_units(df[cfg.TARGET_COL], cfg.SUPPLY_PER_1000_CASES[col])
    np.testing.assert_array_equal(got, df[col].to_numpy())


@pytest.mark.parametrize(("cases", "beds"), [(5, 1), (15, 4), (25, 7), (35, 10)])
def test_bed_ties_round_down_like_the_dataset(cases, beds):
    assert supply_units([cases], cfg.SUPPLY_PER_1000_CASES[cfg.BEDS_COL])[0] == beds


def test_real_valued_forecast_rounds_to_nearest():
    # 2.1 -> 5.0085 bags, 2.3 -> 5.4855, 2.4 -> 5.724
    assert supply_units([2.1, 2.3, 2.4], 2385).tolist() == [5, 5, 6]


def test_negative_forecast_counts_as_zero():
    assert supply_units([-0.7, 0.0], 2385).tolist() == [0, 0]


def test_nan_is_rejected():
    with pytest.raises(ValueError, match="NaN"):
        supply_units([1.0, float("nan")], 2385)


def test_negative_multiplier_is_rejected():
    with pytest.raises(ValueError, match="per_1000"):
        supply_units([1.0], -1)


def test_returns_integers():
    assert supply_units([3.3], 1165).dtype.kind == "i"
