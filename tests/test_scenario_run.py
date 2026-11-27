"""Scenario settings, scenario_id and the end-to-end decision chain (PRD 4)."""
import dataclasses

import pandas as pd
import pytest

from src import config as cfg
from src.ops.pipeline import file_hash, load_context, run_scenario
from src.ops.scenario import Scenario, scenario_id

needs_model = pytest.mark.skipif(
    not (cfg.MODEL_PATH.exists() and cfg.ONSITE_DATA_PATH.exists()),
    reason="trained model or onsite data not present",
)


def test_defaults_are_the_prd_demo_settings():
    s = Scenario()
    assert (s.asof, s.weeks, s.stock_pct, s.floor_pct, s.confidence) == ("2025-06-30", 2, 100, 15, "likely")


def test_scenario_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Scenario().weeks = 3


@pytest.mark.parametrize(
    "bad",
    [
        {"weeks": 5},
        {"stock_pct": 20},
        {"floor_pct": 101},
        {"confidence": "worst"},
        {"crews_total": -1},
        {"crew_mode": "random"},
        {"band": "max"},
    ],
)
def test_invalid_settings_are_rejected(bad):
    with pytest.raises(ValueError):
        Scenario(**bad)


def test_scenario_id_is_short_stable_and_sensitive_to_every_input():
    base = scenario_id(Scenario(), "datahash", "abc1234")
    assert len(base) == 8 and int(base, 16) >= 0
    assert scenario_id(Scenario(), "datahash", "abc1234") == base
    assert scenario_id(Scenario(stock_pct=60), "datahash", "abc1234") != base
    assert scenario_id(Scenario(), "otherdata", "abc1234") != base
    assert scenario_id(Scenario(), "datahash", "def5678") != base


def test_data_hash_ignores_line_endings(tmp_path):
    # git autocrlf gives Windows checkouts CRLF and Linux checkouts LF: same data, same hash.
    lf, crlf, changed = tmp_path / "lf.csv", tmp_path / "crlf.csv", tmp_path / "changed.csv"
    lf.write_bytes(b"a,b\n1,2\n")
    crlf.write_bytes(b"a,b\r\n1,2\r\n")
    changed.write_bytes(b"a,b\n1,3\n")
    assert file_hash(lf) == file_hash(crlf)
    assert file_hash(lf) != file_hash(changed)


@pytest.fixture(scope="module")
def ctx():
    return load_context(git_commit="test")


@needs_model
def test_context_hashes_the_onsite_file(ctx):
    assert len(ctx.data_hash) == 16
    assert len(ctx.wards) == 60 and len(ctx.capacity) == 60


@needs_model
def test_full_stock_without_crews_matches_the_plain_forecast(ctx):
    run = run_scenario(Scenario(crews_total=0), ctx)
    assert (run.crews == 0).all()
    pd.testing.assert_frame_equal(run.plan_window, run.window)
    assert (run.allocation["alert"] == "OK").all()
    need = run.allocation.pivot(index=cfg.WARD_COL, columns="resource", values="need")
    demand = run.demand.set_index(cfg.WARD_COL)
    assert (need[cfg.SALINE_COL] == demand.loc[need.index, cfg.SALINE_COL]).all()


@needs_model
def test_crews_are_capped_by_the_total_and_lower_demand(ctx):
    run = run_scenario(Scenario(crews_total=20), ctx)
    assert run.crews.sum() <= 20
    baseline = run_scenario(Scenario(crews_total=0), ctx)
    assert run.demand[cfg.SALINE_COL].sum() <= baseline.demand[cfg.SALINE_COL].sum()


@needs_model
def test_intervention_can_be_left_out_of_the_plan(ctx):
    run = run_scenario(Scenario(crews_total=20, apply_intervention=False), ctx)
    pd.testing.assert_frame_equal(run.plan_window, run.window)
    assert run.sim["prevented"].sum() > 0


@needs_model
def test_roi_mode_uses_the_auto_suggested_plan(ctx):
    priority = run_scenario(Scenario(crews_total=20, crew_mode="priority"), ctx)
    roi = run_scenario(Scenario(crews_total=20, crew_mode="roi"), ctx)
    assert roi.crews.sum() == 20
    assert roi.sim["prevented"].sum() >= priority.sim["prevented"].sum()


@needs_model
def test_routing_covers_every_ward_and_run_is_deterministic(ctx):
    first = run_scenario(Scenario(stock_pct=60, crews_total=10), ctx)
    second = run_scenario(Scenario(stock_pct=60, crews_total=10), ctx)
    assert len(first.routing.wards) == 60
    assert first.scenario_id == second.scenario_id
    pd.testing.assert_frame_equal(first.allocation, second.allocation)
    pd.testing.assert_frame_equal(first.routing.transfers, second.routing.transfers)
