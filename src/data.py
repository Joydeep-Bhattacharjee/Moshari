"""Load the raw CSV and shape it into one complete row per ward per week."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config as cfg
from src.validate import validate

GAP_FILLED_COL = "is_gap_filled"

# How each column is combined when several rows fall in the same ward-week.
AGGREGATIONS = {
    cfg.CITY_COL: "first",
    **{col: "first" for col in cfg.STATIC_WARD_COLS},
    cfg.RAIN_COL: "sum",
    cfg.TEMP_COL: "mean",
    cfg.TEMP_MAX_COL: "max",
    cfg.TEMP_MIN_COL: "min",
    cfg.HUMIDITY_COL: "mean",
    cfg.TARGET_COL: "sum",
}


def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate rows to Monday-start weeks per ward. Weekly input passes through unchanged."""
    dates = pd.to_datetime(df[cfg.DATE_COL], format="ISO8601").dt.normalize()
    week_start = dates - pd.to_timedelta(dates.dt.weekday, unit="D")
    weekly = (
        df.assign(**{cfg.DATE_COL: week_start})
        .groupby([cfg.WARD_COL, cfg.DATE_COL], as_index=False)
        .agg(AGGREGATIONS)
    )
    return weekly[list(cfg.REQUIRED_COLS)].sort_values(
        [cfg.WARD_COL, cfg.DATE_COL], ignore_index=True
    )


def _fill_ward(ward_df: pd.DataFrame) -> pd.DataFrame:
    full_weeks = pd.date_range(
        ward_df[cfg.DATE_COL].min(), ward_df[cfg.DATE_COL].max(), freq=cfg.DATA_FREQ
    )
    out = ward_df.set_index(cfg.DATE_COL).reindex(full_weeks).rename_axis(cfg.DATE_COL)
    ward_cols = (cfg.WARD_COL, cfg.CITY_COL, *cfg.STATIC_WARD_COLS)
    filled = out.assign(
        **{col: out[col].ffill().bfill() for col in ward_cols},
        **{col: out[col].interpolate(limit_direction="both") for col in cfg.WEATHER_COLS},
        **{GAP_FILLED_COL: out[cfg.WARD_COL].isna()},
    )
    return filled.reset_index()  # target stays NaN in filled weeks: cases are never invented


def fill_gaps(weekly: pd.DataFrame) -> pd.DataFrame:
    """Give every ward a row for every week between its first and last week."""
    frames = [_fill_ward(group) for _, group in weekly.groupby(cfg.WARD_COL, sort=True)]
    return pd.concat(frames, ignore_index=True)[
        [*cfg.REQUIRED_COLS, GAP_FILLED_COL]
    ]


def load_weekly(path: Path = cfg.RAW_DATA_PATH) -> pd.DataFrame:
    """Read, validate, aggregate to weeks and fill gaps. Sorted by ward then date."""
    raw = pd.read_csv(path)
    validate(raw)
    return fill_gaps(to_weekly(raw))
