"""Per-ward weekly features and multi-horizon targets (PRD section 6.2).

Features at week t use only weeks <= t (shift k >= 0); targets use shift(-h).
Thresholds are learned on training weeks only (fit_feature_params).

Usage: python -m src.features
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from src import config as cfg
from src.data import load_weekly
from src.split import holdout_split

RAIN_LAGS = tuple(range(0, 9))
RAIN_ROLL_WINDOWS = (2, 4, 6)
TEMP_LAGS = tuple(range(0, 4))
HUM_LAGS = tuple(range(0, 4))
WINDOW_WEEKS = 4
TEMP_SUITABLE_RANGE_C = (25.0, 32.0)  # Aedes thermal optimum
HEAVY_RAIN_QUANTILE = 0.75
WEEKS_PER_YEAR = 52.1775

FEATURE_GROUPS = {
    "rain": (
        *(f"rain_lag_{k}" for k in RAIN_LAGS),
        *(f"rain_roll_{w}" for w in RAIN_ROLL_WINDOWS),
        "rain_sum_lag2_4",
        "rain_max_4",
        "heavy_rain_weeks_4",
    ),
    "temperature": (*(f"temp_lag_{k}" for k in TEMP_LAGS), "temp_roll_4", "temp_suitable_4"),
    "humidity": (*(f"hum_lag_{k}" for k in HUM_LAGS), "hum_roll_4"),
    "ward": (cfg.WATERLOG_COL, "density_log", cfg.SANITATION_COL),
    "interactions": ("rain2_4_x_waterlog", "rain2_4_x_density", "rain2_4_x_poor_sanitation"),
    "season": ("week_sin", "week_cos"),
}
FEATURE_COLS = tuple(col for cols in FEATURE_GROUPS.values() for col in cols)
KEY_COLS = (cfg.WARD_COL, cfg.CITY_COL, cfg.DATE_COL, cfg.TARGET_COL)


def target_col(horizon: int) -> str:
    return f"y_h{horizon}"


TARGET_COLS = tuple(target_col(h) for h in cfg.HORIZONS)


def _lag(df: pd.DataFrame, col: str, k: int) -> pd.Series:
    return df[col].groupby(df[cfg.WARD_COL]).shift(k)


def _rolling(values: pd.Series, wards: pd.Series, window: int, how: str) -> pd.Series:
    """Trailing window over the current and previous weeks of the same ward."""
    return values.groupby(wards).transform(
        lambda s: getattr(s.rolling(window, min_periods=window), how)()
    )


def fit_feature_params(weekly: pd.DataFrame, train_end) -> dict:
    """Learn data-driven thresholds from weeks <= train_end only."""
    train = weekly[weekly[cfg.DATE_COL] <= pd.Timestamp(train_end)]
    if train.empty:
        raise ValueError(f"no training weeks on or before {train_end}")
    heavy = train.groupby(cfg.WARD_COL)[cfg.RAIN_COL].quantile(HEAVY_RAIN_QUANTILE)
    return {
        "train_end": pd.Timestamp(train_end).date().isoformat(),
        "heavy_rain_mm": {ward: round(float(v), 4) for ward, v in heavy.items()},
    }


def _rain_features(df: pd.DataFrame, params: dict) -> dict:
    wards = df[cfg.WARD_COL]
    cols = {f"rain_lag_{k}": _lag(df, cfg.RAIN_COL, k) for k in RAIN_LAGS}
    for w in RAIN_ROLL_WINDOWS:
        cols[f"rain_roll_{w}"] = _rolling(df[cfg.RAIN_COL], wards, w, "sum")
    cols["rain_sum_lag2_4"] = cols["rain_lag_2"] + cols["rain_lag_3"] + cols["rain_lag_4"]
    cols["rain_max_4"] = _rolling(df[cfg.RAIN_COL], wards, WINDOW_WEEKS, "max")
    heavy = (df[cfg.RAIN_COL] > wards.map(params["heavy_rain_mm"])).astype(float)
    cols["heavy_rain_weeks_4"] = _rolling(heavy, wards, WINDOW_WEEKS, "sum")
    return cols


def _climate_features(df: pd.DataFrame) -> dict:
    wards = df[cfg.WARD_COL]
    cols = {f"temp_lag_{k}": _lag(df, cfg.TEMP_COL, k) for k in TEMP_LAGS}
    cols["temp_roll_4"] = _rolling(df[cfg.TEMP_COL], wards, WINDOW_WEEKS, "mean")
    suitable = df[cfg.TEMP_COL].between(*TEMP_SUITABLE_RANGE_C).astype(float)
    cols["temp_suitable_4"] = _rolling(suitable, wards, WINDOW_WEEKS, "sum")
    cols |= {f"hum_lag_{k}": _lag(df, cfg.HUMIDITY_COL, k) for k in HUM_LAGS}
    cols["hum_roll_4"] = _rolling(df[cfg.HUMIDITY_COL], wards, WINDOW_WEEKS, "mean")
    return cols


def _ward_and_season_features(df: pd.DataFrame, rain_sum_lag2_4: pd.Series) -> dict:
    density_log = np.log1p(df[cfg.DENSITY_COL])
    angle = 2 * np.pi * df[cfg.DATE_COL].dt.isocalendar().week.astype(float) / WEEKS_PER_YEAR
    return {
        cfg.WATERLOG_COL: df[cfg.WATERLOG_COL],
        "density_log": density_log,
        cfg.SANITATION_COL: df[cfg.SANITATION_COL],
        "rain2_4_x_waterlog": rain_sum_lag2_4 * df[cfg.WATERLOG_COL],
        "rain2_4_x_density": rain_sum_lag2_4 * density_log,
        "rain2_4_x_poor_sanitation": rain_sum_lag2_4 * (1 - df[cfg.SANITATION_COL]),
        "week_sin": np.sin(angle),
        "week_cos": np.cos(angle),
    }


def build_features(weekly: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Return keys + FEATURE_COLS + TARGET_COLS, one row per (ward, week). Input is not modified."""
    unknown = set(weekly[cfg.WARD_COL]) - set(params["heavy_rain_mm"])
    if unknown:
        raise ValueError(f"wards missing from feature params: {sorted(unknown)[:5]}")
    df = weekly.sort_values([cfg.WARD_COL, cfg.DATE_COL], ignore_index=True)
    rain = _rain_features(df, params)
    cols = {
        **rain,
        **_climate_features(df),
        **_ward_and_season_features(df, rain["rain_sum_lag2_4"]),
    }
    targets = {target_col(h): _lag(df, cfg.TARGET_COL, -h) for h in cfg.HORIZONS}
    features = pd.DataFrame({col: cols[col] for col in FEATURE_COLS})
    leaked = [c for c in FEATURE_COLS if c.startswith("y_") or c == cfg.TARGET_COL]
    assert not leaked, f"target columns used as features: {leaked}"
    return pd.concat([df[list(KEY_COLS)], features, pd.DataFrame(targets)], axis=1)


def main() -> int:
    weekly = load_weekly()
    split = holdout_split(weekly[cfg.DATE_COL])
    params = fit_feature_params(weekly, split.train_end)
    features = build_features(weekly, params)
    cfg.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    features.to_csv(cfg.FEATURES_PATH, index=False, float_format="%.4f")
    cfg.FEATURE_PARAMS_PATH.write_text(json.dumps(params, indent=2), encoding="utf-8")
    print(f"wrote {cfg.FEATURES_PATH} {features.shape}, {len(FEATURE_COLS)} features")
    print(f"thresholds fit on weeks <= {params['train_end']}; holdout starts {split.holdout_start.date()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
