"""Lag-proof analysis (PRD section 6.3): does rain k weeks ago track cases now?

Computed on training weeks only, so the holdout stays untouched.
Usage: python -m src.eda
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from src import config as cfg
from src.data import load_weekly
from src.split import holdout_split

MAX_LAG_WEEKS = 8


def _spearman(a: pd.Series, b: pd.Series) -> float:
    both = a.notna() & b.notna()
    return float(a[both].rank().corr(b[both].rank()))


def _remove_season(df: pd.DataFrame, col: str) -> pd.Series:
    """Subtract each ward's mean for that ISO week, so the monsoon cycle alone cannot correlate."""
    week = df[cfg.DATE_COL].dt.isocalendar().week
    return df[col] - df.groupby([df[cfg.WARD_COL], week])[col].transform("mean")


def lag_correlation(weekly: pd.DataFrame, max_lag: int = MAX_LAG_WEEKS) -> pd.DataFrame:
    """Pooled Spearman(rain at t-k, cases at t) per lag k, raw and season-removed."""
    df = weekly.sort_values([cfg.WARD_COL, cfg.DATE_COL], ignore_index=True)
    wards = df[cfg.WARD_COL]
    rain_anom = _remove_season(df, cfg.RAIN_COL)
    cases_anom = _remove_season(df, cfg.TARGET_COL)
    rows = [
        {
            "lag_weeks": k,
            "spearman_raw": round(_spearman(df[cfg.RAIN_COL].groupby(wards).shift(k), df[cfg.TARGET_COL]), 4),
            "spearman_deseasonalized": round(_spearman(rain_anom.groupby(wards).shift(k), cases_anom), 4),
        }
        for k in range(max_lag + 1)
    ]
    return pd.DataFrame(rows)


def update_meta(updates: dict, path: Path = cfg.META_PATH) -> dict:
    """Merge top-level keys into meta.json, keeping keys written by other steps."""
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    merged = {**current, **updates}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def _summary(table: pd.DataFrame, train: pd.DataFrame) -> dict:
    def peak(col: str) -> int:
        return int(table.loc[table[col].idxmax(), "lag_weeks"])

    return {
        "period": [train[cfg.DATE_COL].min().date().isoformat(), train[cfg.DATE_COL].max().date().isoformat()],
        "method": "pooled Spearman over ward-weeks; deseasonalized = minus ward x ISO-week mean",
        "lags": table["lag_weeks"].tolist(),
        "spearman_raw": table["spearman_raw"].tolist(),
        "spearman_deseasonalized": table["spearman_deseasonalized"].tolist(),
        "peak_lag_raw": peak("spearman_raw"),
        "peak_lag_deseasonalized": peak("spearman_deseasonalized"),
    }


def main() -> int:
    weekly = load_weekly()
    split = holdout_split(weekly[cfg.DATE_COL])
    train = weekly[weekly[cfg.DATE_COL] <= split.train_end]
    table = lag_correlation(train)
    summary = _summary(table, train)
    update_meta({"lag_correlation": summary})
    print(table.to_string(index=False))
    print(f"peak lag: raw={summary['peak_lag_raw']} wk, season removed={summary['peak_lag_deseasonalized']} wk")
    print(f"saved to {cfg.META_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
