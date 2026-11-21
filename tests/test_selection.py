import json

import pytest

from src import config as cfg
from src.backtest import fold_frames
from src.models import ModelSpec
from src.selection import keep_monotonic, lag_gain_pct, select_horizon
from src.split import walk_forward_folds
from src.train import load_selection


def test_keep_monotonic_within_two_percent():
    assert keep_monotonic(1.0, 1.02)
    assert keep_monotonic(1.0, 0.9)
    assert not keep_monotonic(1.0, 1.0201)


def test_lag_gain_is_percent_of_no_lag_rmse():
    assert lag_gain_pct(3.0, 4.0) == 25.0


def test_select_horizon_smoke(make_weekly):
    weekly = make_weekly(n_wards=3, n_weeks=80)
    folds = walk_forward_folds(weekly[cfg.DATE_COL], n_folds=2, test_weeks=8, min_train_weeks=20)
    result = select_horizon(2, fold_frames(weekly, folds))
    names = {row["model"] for row in result["candidates"]}
    assert result["chosen"]["name"] in names
    assert {"B1_ward_mean", "B2_seasonal_naive"} <= names
    assert isinstance(result["beats_baselines"], bool)
    assert 0.5 <= result["alerts"]["decision_scale"] <= 1.0
    assert result["lag_ablation"]["model"].endswith("no_lagged_rain")
    assert len(result["per_fold"]) == 2


def test_load_selection_reads_chosen_specs(tmp_path):
    chosen = {"family": "hgb_poisson", "learning_rate": 0.1, "monotonic": True, "feature_set": "all", "name": "x"}
    meta = {"model_selection": {"horizons": {"3": {"chosen": chosen, "alerts": {"decision_scale": 0.8}}}}}
    path = tmp_path / "meta.json"
    path.write_text(json.dumps(meta), encoding="utf-8")
    selection = load_selection(path)
    assert selection == {3: {"spec": ModelSpec("hgb_poisson", 0.1, True, "all"), "decision_scale": 0.8}}


def test_load_selection_without_selection_step_fails(tmp_path):
    with pytest.raises(RuntimeError, match="src.selection"):
        load_selection(tmp_path / "missing.json")
