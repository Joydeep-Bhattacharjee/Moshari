
"""Tests for the dengue dataset validation module."""

import pandas as pd
import pytest

from src.validate import validate_dataframe


@pytest.fixture
def valid_dataset():
    """Create a small valid ward-week dataset."""
    return pd.DataFrame({
        "date": ["2024-01-01", "2024-01-08"],
        "city": ["Chattogram", "Chattogram"],
        "ward_id": ["WARD_01", "WARD_01"],
        "population_density_sqkm": [64000, 64000],
        "water_logging_risk_index": [0.87, 0.87],
        "sanitation_score": [0.46, 0.46],
        "avg_temp_c": [25.0, 26.0],
        "max_temp_c": [30.0, 31.0],
        "min_temp_c": [20.0, 21.0],
        "rainfall_mm": [2.0, 5.0],
        "relative_humidity_pct": [70.0, 75.0],
        "dengue_cases": [0, 3],
    })


def test_valid_dataset_passes(valid_dataset):
    result = validate_dataframe(valid_dataset)

    assert len(result) == 2
    assert pd.api.types.is_datetime64_any_dtype(result["date"])


def test_missing_required_column_fails(valid_dataset):
    invalid = valid_dataset.drop(columns=["rainfall_mm"])

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_dataframe(invalid)


def test_missing_values_fail(valid_dataset):
    invalid = valid_dataset.copy()
    invalid.loc[0, "avg_temp_c"] = None

    with pytest.raises(ValueError, match="Missing values detected"):
        validate_dataframe(invalid)


def test_invalid_date_fails(valid_dataset):
    invalid = valid_dataset.copy()
    invalid.loc[0, "date"] = "not-a-date"

    with pytest.raises(ValueError, match="Invalid or missing date"):
        validate_dataframe(invalid)


def test_duplicate_ward_date_fails(valid_dataset):
    invalid = pd.concat(
        [valid_dataset, valid_dataset.iloc[[0]]],
        ignore_index=True
    )

    with pytest.raises(ValueError, match="duplicate ward-date"):
        validate_dataframe(invalid)


def test_negative_dengue_cases_fail(valid_dataset):
    invalid = valid_dataset.copy()
    invalid.loc[0, "dengue_cases"] = -1

    with pytest.raises(ValueError, match="cannot be negative"):
        validate_dataframe(invalid)


def test_fractional_dengue_cases_fail(valid_dataset):
    invalid = valid_dataset.copy()
    invalid["dengue_cases"] = invalid["dengue_cases"].astype(float)
    invalid.loc[0, "dengue_cases"] = 1.5

    with pytest.raises(ValueError, match="must be integers"):
        validate_dataframe(invalid)


def test_static_feature_inconsistency_fails(valid_dataset):
    invalid = valid_dataset.copy()
    invalid.loc[1, "sanitation_score"] = 0.90

    with pytest.raises(ValueError, match="sanitation_score"):
        validate_dataframe(invalid)


def test_empty_dataset_fails():
    with pytest.raises(ValueError, match="Dataset is empty"):
        validate_dataframe(pd.DataFrame())


def test_input_is_not_modified(valid_dataset):
    original = valid_dataset.copy(deep=True)

    validate_dataframe(valid_dataset)

    pd.testing.assert_frame_equal(valid_dataset, original)
