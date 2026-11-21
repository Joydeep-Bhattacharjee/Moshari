
"""Dataset validation utilities for Dengue Radar."""

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "date",
    "city",
    "ward_id",
    "population_density_sqkm",
    "water_logging_risk_index",
    "sanitation_score",
    "avg_temp_c",
    "max_temp_c",
    "min_temp_c",
    "rainfall_mm",
    "relative_humidity_pct",
    "dengue_cases",
]

STATIC_COLUMNS = [
    "city",
    "population_density_sqkm",
    "water_logging_risk_index",
    "sanitation_score",
]

DATE_COLUMN = "date"
WARD_COLUMN = "ward_id"
TARGET_COLUMN = "dengue_cases"


def validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalize the dengue dataset.

    Returns a copy with the date column converted to datetime.

    Raises:
        ValueError: If one or more data validation checks fail.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    if df.empty:
        raise ValueError("Dataset is empty.")

    errors = []

    # 1. Check required columns
    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    validated = df.copy()

    # 2. Check missing values
    missing_values = validated[REQUIRED_COLUMNS].isna().sum()
    columns_with_missing = missing_values[missing_values > 0]

    if not columns_with_missing.empty:
        errors.append(
            f"Missing values detected: {columns_with_missing.to_dict()}"
        )

    # 3. Validate and convert dates
    parsed_dates = pd.to_datetime(
    validated[DATE_COLUMN],
    format="mixed",
    errors="coerce"
)

    if parsed_dates.isna().any():
        errors.append("Invalid or missing date values detected.")
    else:
        validated[DATE_COLUMN] = parsed_dates

    # 4. Check duplicate ward-date combinations
    duplicate_mask = validated.duplicated(
        subset=[DATE_COLUMN, WARD_COLUMN],
        keep=False
    )

    if duplicate_mask.any():
        errors.append(
            f"Found {int(duplicate_mask.sum())} rows with "
            "duplicate ward-date combinations."
        )

    # 5. Validate dengue case counts
    cases = pd.to_numeric(
        validated[TARGET_COLUMN],
        errors="coerce"
    )

    if cases.isna().any():
        errors.append("Dengue case counts must be numeric.")
    elif (cases < 0).any():
        errors.append("Dengue case counts cannot be negative.")
    elif (cases % 1 != 0).any():
        errors.append("Dengue case counts must be integers.")

    # 6. Check ward-level static features
    for column in STATIC_COLUMNS:
        inconsistent_wards = (
            validated.groupby(WARD_COLUMN)[column]
            .nunique(dropna=False)
        )

        inconsistent_wards = inconsistent_wards[
            inconsistent_wards > 1
        ]

        if not inconsistent_wards.empty:
            errors.append(
                f"Static feature '{column}' changes across "
                f"observations for wards: "
                f"{inconsistent_wards.index.tolist()}"
            )

    if errors:
        raise ValueError(
            "Dataset validation failed:\n- "
            + "\n- ".join(errors)
        )

    validated[TARGET_COLUMN] = cases.astype("int64")

    return validated


def load_and_validate(csv_path: str | Path) -> pd.DataFrame:
    """Load a CSV file and validate its contents."""
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {csv_path}"
        )

    df = pd.read_csv(csv_path)

    return validate_dataframe(df)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    dataset_path = project_root / "data" / "raw" / "dengue.csv"

    validated_df = load_and_validate(dataset_path)

    print("Dataset validation successful!")
    print(f"Rows: {len(validated_df):,}")
    print(f"Columns: {len(validated_df.columns)}")
    print(f"Wards: {validated_df[WARD_COLUMN].nunique()}")
    print(
        f"Date range: {validated_df[DATE_COLUMN].min().date()} "
        f"to {validated_df[DATE_COLUMN].max().date()}"
    )
