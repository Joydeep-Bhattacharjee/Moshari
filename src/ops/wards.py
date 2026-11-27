"""Static ward attributes (density, water-logging, sanitation): one row per ward."""
from __future__ import annotations

import pandas as pd

from src import config as cfg

WARD_ATTRIBUTE_COLS = (cfg.WARD_COL, cfg.CITY_COL, *cfg.STATIC_WARD_COLS)


def ward_attributes(weekly: pd.DataFrame) -> pd.DataFrame:
    """City and static indices per ward, sorted by ward_id; raises if any of them varies."""
    grouped = weekly.groupby(cfg.WARD_COL, sort=True)
    varying = [c for c in (cfg.CITY_COL, *cfg.STATIC_WARD_COLS) if (grouped[c].nunique() > 1).any()]
    if varying:
        raise ValueError(f"ward attributes change over time: {varying}")
    return grouped[[cfg.CITY_COL, *cfg.STATIC_WARD_COLS]].first().reset_index()[list(WARD_ATTRIBUTE_COLS)]
