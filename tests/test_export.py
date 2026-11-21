import json

import pandas as pd
import pytest

from src import config as cfg
from src.data import load_weekly
from src.export import MULTIPLIERS, OUT_DIR, alert_counts, build_dashboard, build_validation
from src.features import FEATURE_COLS, build_features
from src.predict import load_bundle
from src.scenario import run_scenario, scale_recent_rain_features

pytestmark = pytest.mark.skipif(not cfg.MODEL_PATH.exists(), reason="trained model not present")

MONSOON = "2025-08-04"


@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


@pytest.fixture(scope="module")
def weekly():
    return load_weekly()


@pytest.fixture(scope="module")
def meta():
    return json.loads(cfg.META_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def monsoon_rows(bundle, weekly):
    frame = build_features(weekly, bundle["feature_params"])
    return frame[frame[cfg.DATE_COL] == pd.Timestamp(MONSOON)]


def test_alert_counts_collapse_tiers_at_high():
    confusion = [[10, 1, 0, 0], [2, 5, 1, 0], [0, 1, 3, 1], [0, 0, 1, 4]]
    assert alert_counts(confusion) == {"tn": 18, "fp": 1, "fn": 1, "tp": 9}


def test_fast_scenario_matches_rebuilding_features(bundle, weekly, monsoon_rows):
    for multiplier in (0.5, 2.0):
        fast = scale_recent_rain_features(monsoon_rows, multiplier, bundle["feature_params"])
        for horizon in cfg.HORIZONS:
            preds = bundle["models"][horizon]["point"].predict(fast)
            for j, ward in list(enumerate(monsoon_rows[cfg.WARD_COL]))[::15]:
                slow = run_scenario(weekly, bundle, ward, MONSOON, horizon, multiplier)
                assert preds[j] == pytest.approx(slow["scenario"]["predicted_cases"], abs=1e-9)


def test_multiplier_one_changes_no_feature(bundle, monsoon_rows):
    same = scale_recent_rain_features(monsoon_rows, 1.0, bundle["feature_params"])
    pd.testing.assert_frame_equal(same[list(FEATURE_COLS)], monsoon_rows[list(FEATURE_COLS)])


def test_dashboard_arrays_align_and_serialize(bundle, weekly, meta):
    dashboard = build_dashboard(weekly, bundle, meta)
    n = len(dashboard["weeks"])
    scenario_keys = {f"{m:g}" for m in MULTIPLIERS if m != 1.0}
    assert len(dashboard["wards"]) == 60
    for horizon in cfg.HORIZONS:
        for ward, block in dashboard["forecasts"][str(horizon)].items():
            assert {len(block[k]) for k in ("pred", "lo", "hi", "actual", "drivers")} == {n}, ward
            assert all(len(d) == 6 for d in block["drivers"])
            assert set(block["scenario"]) == scenario_keys
            assert all(lo <= p <= hi for lo, p, hi in zip(block["lo"], block["pred"], block["hi"]))
    json.dumps(dashboard, allow_nan=False)


def test_validation_counts_cover_every_holdout_week(meta):
    validation = build_validation(meta)
    for horizon, result in validation["horizons"].items():
        counts = result["holdout"]
        assert counts["tn"] + counts["fp"] + counts["fn"] + counts["tp"] == meta["holdout"][horizon]["n"]


def test_committed_frontend_data_matches_meta(meta):
    """Re-run `python -m src.export` after retraining, or the dashboard shows stale numbers."""
    committed = json.loads((OUT_DIR / "validation.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(build_validation(meta)))
