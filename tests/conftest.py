import numpy as np
import pandas as pd
import pytest

from src import config as cfg


def _make_weekly(n_wards: int = 2, n_weeks: int = 20, start: str = "2020-01-06") -> pd.DataFrame:
    """Clean weekly panel; each ward's values are distinct so cross-ward leaks are visible."""
    dates = pd.date_range(start, periods=n_weeks, freq=cfg.DATA_FREQ)
    step = np.arange(n_weeks, dtype=float)
    frames = [
        pd.DataFrame(
            {
                cfg.DATE_COL: dates,
                cfg.CITY_COL: "Dhaka North",
                cfg.WARD_COL: f"W{ward}",
                cfg.DENSITY_COL: 40000.0 + 1000 * ward,
                cfg.WATERLOG_COL: 0.3 + 0.2 * ward,
                cfg.SANITATION_COL: 0.7 - 0.2 * ward,
                cfg.TEMP_COL: 22.0 + step % 12,
                cfg.TEMP_MAX_COL: 30.0 + step % 12,
                cfg.TEMP_MIN_COL: 18.0 + step % 12,
                cfg.RAIN_COL: 10.0 * step + 1000.0 * ward,
                cfg.HUMIDITY_COL: 60.0 + step + 10 * ward,
                cfg.TARGET_COL: step + 100.0 * ward,
            }
        )
        for ward in range(n_wards)
    ]
    return pd.concat(frames, ignore_index=True)[list(cfg.REQUIRED_COLS)]


@pytest.fixture
def make_weekly():
    return _make_weekly


@pytest.fixture
def weekly():
    return _make_weekly()
