"""Data contract for the onsite dataset (Phase 2).

The onsite file must be the Phase 1 dataset plus three supply columns. If any
Phase 1 value changed, the trained model and its holdout metrics would no
longer be valid, so that equality is checked cell by cell.
"""
from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal

import pandas as pd
import pytest

from src import config as cfg
from src.validate import validate

pytestmark = pytest.mark.skipif(
    not (cfg.ONSITE_DATA_PATH.exists() and cfg.RAW_DATA_PATH.exists()),
    reason="onsite or Phase 1 raw data not present",
)

N_WARDS = 60
N_WEEKS = 522


@pytest.fixture(scope="module")
def onsite() -> pd.DataFrame:
    return pd.read_csv(cfg.ONSITE_DATA_PATH)


@pytest.fixture(scope="module")
def phase1() -> pd.DataFrame:
    return pd.read_csv(cfg.RAW_DATA_PATH)


def test_onsite_passes_phase1_contract(onsite):
    validate(onsite)


def test_onsite_columns_are_phase1_plus_supply(onsite, phase1):
    assert list(onsite.columns) == [*phase1.columns, *cfg.SUPPLY_COLS]


def test_onsite_is_complete_balanced_panel(onsite):
    assert onsite[cfg.WARD_COL].nunique() == N_WARDS
    assert onsite[cfg.DATE_COL].nunique() == N_WEEKS
    assert len(onsite) == N_WARDS * N_WEEKS
    assert not onsite.duplicated([cfg.WARD_COL, cfg.DATE_COL]).any()


def test_phase1_columns_unchanged_so_model_stays_valid(onsite, phase1):
    pd.testing.assert_frame_equal(onsite[phase1.columns], phase1)


def test_supply_columns_are_non_negative_integers(onsite):
    supply = onsite[list(cfg.SUPPLY_COLS)]
    assert not supply.isna().any().any()
    assert all(pd.api.types.is_integer_dtype(supply[col]) for col in cfg.SUPPLY_COLS)
    assert (supply >= 0).all().all()


def test_no_supply_needed_when_no_cases(onsite):
    no_cases = onsite[onsite[cfg.TARGET_COL] == 0]
    assert (no_cases[list(cfg.SUPPLY_COLS)] == 0).all().all()


def _decimal_supply(cases: int, per_1000: int, rounding: str) -> int:
    """Independent oracle: exact decimal product, then round to an integer."""
    exact = Decimal(per_1000) / 1000 * cases
    return int(exact.quantize(Decimal(1), rounding=rounding))


def _mismatches(onsite: pd.DataFrame, col: str, rounding: str) -> int:
    per_1000 = cfg.SUPPLY_PER_1000_CASES[col]
    expected = onsite[cfg.TARGET_COL].map(lambda c: _decimal_supply(int(c), per_1000, rounding))
    return int((expected != onsite[col]).sum())


@pytest.mark.parametrize("col", cfg.SUPPLY_COLS)
def test_supply_is_multiplier_rounded_half_down_on_every_row(onsite, col):
    assert _mismatches(onsite, col, ROUND_HALF_DOWN) == 0


def test_beds_ties_prove_half_up_is_wrong(onsite):
    """Guards the PRD/data conflict: the PRD says half-up, the data rounds .5 down."""
    assert _mismatches(onsite, cfg.BEDS_COL, ROUND_HALF_UP) > 0
