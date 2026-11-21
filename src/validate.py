"""Validate the raw dengue CSV against the data contract and print a quality report.

Usage: python -m src.validate [--path data/raw/dengue.csv]
Exit code 1 when any rule fails.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src import config as cfg


class DataValidationError(ValueError):
    """Raised when the raw data breaks the data contract. Lists every failure."""

    def __init__(self, errors: list[str]):
        self.errors = tuple(errors)
        super().__init__("Data validation failed:\n- " + "\n- ".join(errors))


def _numeric(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def _parsed_dates(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df[cfg.DATE_COL], errors="coerce", format="ISO8601")


def _check_missing(df: pd.DataFrame) -> list[str]:
    counts = df[list(cfg.REQUIRED_COLS)].isna().sum()
    bad = counts[counts > 0]
    return [f"missing values: {bad.to_dict()}"] if len(bad) else []


def _check_numeric(df: pd.DataFrame) -> list[str]:
    errors = []
    for col in cfg.NUMERIC_COLS:
        n_bad = int((_numeric(df, col).isna() & df[col].notna()).sum())
        if n_bad:
            errors.append(f"{col}: {n_bad} non-numeric values")
    return errors


def _check_ranges(df: pd.DataFrame) -> list[str]:
    errors = []
    for col, (low, high) in cfg.RANGE_RULES.items():
        values = _numeric(df, col)
        below = int((values < low).sum()) if low is not None else 0
        above = int((values > high).sum()) if high is not None else 0
        if below or above:
            errors.append(f"{col}: {below + above} values outside [{low}, {high}]")
    density = _numeric(df, cfg.DENSITY_COL)
    if (density <= 0).any():
        errors.append(f"{cfg.DENSITY_COL}: {int((density <= 0).sum())} values <= 0")
    target = _numeric(df, cfg.TARGET_COL)
    n_fractional = int((target.dropna() % 1 != 0).sum())
    if n_fractional:
        errors.append(f"{cfg.TARGET_COL}: {n_fractional} non-integer counts")
    return errors


def _check_keys(df: pd.DataFrame) -> list[str]:
    errors = []
    dates = _parsed_dates(df)
    n_unparsed = int((dates.isna() & df[cfg.DATE_COL].notna()).sum())
    if n_unparsed:
        errors.append(f"{cfg.DATE_COL}: {n_unparsed} values do not parse as dates")
    keys = pd.DataFrame({"ward": df[cfg.WARD_COL], "date": dates})
    n_dup = int(keys.duplicated().sum())
    if n_dup:
        errors.append(f"{n_dup} duplicate ({cfg.WARD_COL}, {cfg.DATE_COL}) rows")
    weeks = keys.dropna().groupby("ward")["date"].nunique()
    short = weeks[weeks < cfg.MIN_WEEKS_PER_WARD]
    if len(short):
        errors.append(
            f"{len(short)} wards with < {cfg.MIN_WEEKS_PER_WARD} weeks: {sorted(short.index)[:5]}"
        )
    return errors


def validate(df: pd.DataFrame) -> None:
    """Raise DataValidationError listing every contract violation. Does not modify df."""
    missing_cols = [c for c in cfg.REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        raise DataValidationError([f"missing required columns: {missing_cols}"])
    errors = _check_missing(df) + _check_numeric(df) + _check_ranges(df) + _check_keys(df)
    if errors:
        raise DataValidationError(errors)


def _spearman(a: pd.Series, b: pd.Series) -> float:
    if a.nunique() < 2 or b.nunique() < 2:
        return float("nan")  # undefined when a column is constant
    return float(a.rank().corr(b.rank()))


def quality_report(df: pd.DataFrame) -> dict:
    """Summarise shape, coverage and ward-level facts. Assumes validate(df) passed."""
    dates = _parsed_dates(df)
    per_ward = df.assign(_date=dates).groupby(cfg.WARD_COL)
    gaps_days = per_ward["_date"].apply(lambda s: s.sort_values().diff().dt.days.dropna())
    ward_means = per_ward[[*cfg.STATIC_WARD_COLS, cfg.TARGET_COL]].mean()
    target = _numeric(df, cfg.TARGET_COL)
    return {
        "rows": len(df),
        "columns": list(df.columns),
        "cities": df[cfg.CITY_COL].value_counts().to_dict(),
        "n_wards": int(df[cfg.WARD_COL].nunique()),
        "date_min": dates.min().date().isoformat(),
        "date_max": dates.max().date().isoformat(),
        "rows_per_ward": (int(per_ward.size().min()), int(per_ward.size().max())),
        "gap_days": sorted(gaps_days.unique().astype(int).tolist()),
        "target_zero_share": round(float((target == 0).mean()), 4),
        "target_max": int(target.max()),
        "static_per_ward": {
            col: bool((per_ward[col].nunique() == 1).all()) for col in cfg.STATIC_WARD_COLS
        },
        "ward_spearman_vs_mean_cases": {
            col: round(_spearman(ward_means[col], ward_means[cfg.TARGET_COL]), 3)
            for col in cfg.STATIC_WARD_COLS
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the raw dengue CSV.")
    parser.add_argument("--path", type=Path, default=cfg.RAW_DATA_PATH)
    args = parser.parse_args(argv)
    try:
        df = pd.read_csv(args.path)
        validate(df)
    except FileNotFoundError:
        print(f"Data file not found: {args.path}", file=sys.stderr)
        return 1
    except DataValidationError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"OK: {args.path} passed all validation rules\n")
    for key, value in quality_report(df).items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
