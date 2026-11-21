import json

import numpy as np
import pandas as pd

from src import config as cfg
from src.eda import lag_correlation, update_meta


def test_peak_found_at_true_lag(make_weekly):
    weekly = make_weekly(n_wards=3, n_weeks=120)
    rng = np.random.default_rng(42)
    rain = pd.Series(rng.gamma(2.0, 20.0, len(weekly)))
    cases = rain.groupby(weekly[cfg.WARD_COL]).shift(3).fillna(0) / 10
    table = lag_correlation(weekly.assign(**{cfg.RAIN_COL: rain, cfg.TARGET_COL: cases}))
    assert table.loc[table["spearman_raw"].idxmax(), "lag_weeks"] == 3
    assert table.loc[table["spearman_deseasonalized"].idxmax(), "lag_weeks"] == 3


def test_update_meta_keeps_existing_keys(tmp_path):
    path = tmp_path / "meta.json"
    path.write_text(json.dumps({"backtest": [1, 2]}), encoding="utf-8")
    merged = update_meta({"lag_correlation": {"peak_lag_raw": 3}}, path)
    assert merged == {"backtest": [1, 2], "lag_correlation": {"peak_lag_raw": 3}}
    assert json.loads(path.read_text(encoding="utf-8")) == merged
