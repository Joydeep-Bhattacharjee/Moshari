import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src import config as cfg

pytestmark = pytest.mark.skipif(not cfg.MODEL_PATH.exists(), reason="trained model not present")

APP = str(cfg.ROOT / "app.py")


@pytest.fixture(scope="module")
def app():
    return AppTest.from_file(APP, default_timeout=120).run()


def _problems(at: AppTest) -> list:
    return [e.value for e in at.exception] + [w.value for w in at.warning] + [e.value for e in at.error]


def test_app_starts_with_four_tabs_and_no_errors(app):
    assert _problems(app) == []
    assert [t.label for t in app.tabs] == ["Forecast", "Priority list", "Validation", "About"]


def test_footer_states_zero_api_calls(app):
    assert any("0 API calls · 0 LLM tokens" in m.value for m in app.markdown)


@pytest.mark.parametrize("horizon", cfg.HORIZONS)
def test_monsoon_week_with_rain_scenario_renders_for_every_horizon(app, horizon):
    app.select_slider[0].set_value(pd.Timestamp("2025-08-04"))
    app.slider[0].set_value(2.0)
    app.radio[0].set_value(horizon)
    app.run()
    assert _problems(app) == []
    labels = [m.label for m in app.metric]
    assert {"Predicted cases", "80% range", "Change", "Alert recall (holdout)"} <= set(labels)


def test_every_ward_renders(app):
    app.select_slider[0].set_value(pd.Timestamp("2025-08-04"))
    for ward in app.selectbox[0].options[::12]:
        app.selectbox[0].set_value(ward.split(" · ")[0])
        app.run()
        assert _problems(app) == [], ward
