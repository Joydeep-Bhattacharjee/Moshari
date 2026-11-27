"""The committed Python -> TypeScript fixtures must match what the Python core produces now."""
import json
import math

import pytest

from src import config as cfg
from src.ops.parity import FIXTURE_PATH, PARITY_SCENARIOS, build_fixtures, dashboard_commit
from src.ops.pipeline import load_context
from src.ops.ui_export import OUT_DIR

pytestmark = pytest.mark.skipif(
    not (cfg.MODEL_PATH.exists() and cfg.ONSITE_DATA_PATH.exists() and (OUT_DIR / "config.json").exists()),
    reason="model, onsite data or dashboard config not present",
)


def assert_same(committed, fresh, path: str = "fixtures") -> None:
    """Exact for text, integers and structure; floats to 1e-9 relative, because model
    predictions can differ in the last bit between platforms' BLAS builds."""
    if isinstance(committed, float) or isinstance(fresh, float):
        assert math.isclose(committed, fresh, rel_tol=1e-9, abs_tol=1e-12), path
    elif isinstance(fresh, dict):
        assert committed.keys() == fresh.keys(), path
        for key in fresh:
            assert_same(committed[key], fresh[key], f"{path}.{key}")
    elif isinstance(fresh, list):
        assert len(committed) == len(fresh), path
        for i, (a, b) in enumerate(zip(committed, fresh)):
            assert_same(a, b, f"{path}[{i}]")
    else:
        assert committed == fresh, f"{path}: fixtures are stale, run python -m src.ops.parity"


def test_committed_fixtures_are_up_to_date():
    assert FIXTURE_PATH.exists(), "run python -m src.ops.parity"
    committed = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(build_fixtures(load_context(git_commit=dashboard_commit()))))
    assert_same(committed, fresh)


def test_scenarios_cover_every_setting():
    settings = {field: {getattr(s, field) for s in PARITY_SCENARIOS} for field in vars(PARITY_SCENARIOS[0])}
    assert settings["confidence"] == {"likely", "bad"}
    assert settings["crew_mode"] == {"priority", "roi"}
    assert settings["band"] == {"low", "base", "high"}
    assert settings["apply_intervention"] == {True, False}
    assert settings["weeks"] == {1, 2, 3, 4}
