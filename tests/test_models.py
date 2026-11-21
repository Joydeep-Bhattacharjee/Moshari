import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from src import config as cfg
from src.features import FEATURE_COLS, build_features, fit_feature_params
from src.models import (
    FEATURE_SETS,
    LAGGED_RAIN_COLS,
    MONOTONIC,
    FeatureModel,
    ModelSpec,
    clip_interval,
    make_model,
)


@pytest.fixture
def train_frame(make_weekly):
    weekly = make_weekly(n_wards=3, n_weeks=40)
    features = build_features(weekly, fit_feature_params(weekly, weekly[cfg.DATE_COL].max()))
    return features[features["y_h2"].notna()]


@pytest.mark.parametrize(
    "spec",
    [
        ModelSpec("glm_poisson"),
        ModelSpec("hgb_poisson"),
        ModelSpec("hgb_log"),
        ModelSpec("hgb_poisson", monotonic=True),
        ModelSpec("hgb_poisson", feature_set="no_lagged_rain"),
    ],
    ids=lambda s: s.name,
)
def test_each_model_fits_and_never_predicts_negative(spec, train_frame):
    model = make_model(spec).fit(train_frame, train_frame["y_h2"])
    pred = model.predict(train_frame)
    assert pred.shape == (len(train_frame),)
    assert (pred >= 0).all()


def test_quantile_model_uses_quantile_loss():
    model = make_model(ModelSpec("hgb_log", learning_rate=0.1), quantile=0.9)
    assert model.estimator.loss == "quantile"
    assert model.estimator.quantile == 0.9
    assert model.estimator.learning_rate == 0.1
    assert not model.log_target


def test_monotonic_constraints_follow_confirmed_directions():
    estimator = make_model(ModelSpec("hgb_poisson", monotonic=True)).estimator
    constraints = dict(zip(FEATURE_COLS, estimator.monotonic_cst))
    assert constraints["rain_sum_lag2_4"] == 1
    assert constraints[cfg.WATERLOG_COL] == 1
    assert constraints[cfg.SANITATION_COL] == -1
    assert sum(v != 0 for v in constraints.values()) == len(MONOTONIC)


def test_unconstrained_model_has_no_constraints():
    assert make_model(ModelSpec("hgb_poisson")).estimator.monotonic_cst is None


def test_feature_model_ignores_extra_columns(train_frame):
    spec = ModelSpec("hgb_poisson")
    plain = make_model(spec).fit(train_frame, train_frame["y_h2"]).predict(train_frame)
    noisy = train_frame.assign(junk=np.arange(len(train_frame)))
    with_junk = make_model(spec).fit(noisy, noisy["y_h2"]).predict(noisy)
    np.testing.assert_allclose(plain, with_junk)


def test_log_target_is_inverted_on_predict():
    frame = pd.DataFrame({"x": np.linspace(0, 2, 30)})
    y = pd.Series(np.expm1(1.5 * frame["x"]))
    model = FeatureModel(LinearRegression(), ("x",), log_target=True).fit(frame, y)
    np.testing.assert_allclose(model.predict(frame), y, rtol=1e-6, atol=1e-9)


def test_no_lagged_rain_set_keeps_only_current_week_rain():
    subset = FEATURE_SETS["no_lagged_rain"]
    assert "rain_lag_0" in subset
    assert not set(LAGGED_RAIN_COLS) & set(subset)
    assert set(subset) | set(LAGGED_RAIN_COLS) == set(FEATURE_COLS)


def test_spec_names_are_unique_and_unknown_family_fails():
    specs = [
        ModelSpec("glm_poisson"),
        ModelSpec("hgb_poisson", 0.03),
        ModelSpec("hgb_poisson", 0.05),
        ModelSpec("hgb_poisson", 0.05, monotonic=True),
        ModelSpec("hgb_log", 0.05),
        ModelSpec("hgb_log", 0.05, feature_set="no_lagged_rain"),
    ]
    assert len({s.name for s in specs}) == len(specs)
    with pytest.raises(ValueError, match="unknown model family"):
        make_model(ModelSpec("random_forest"))


def test_clip_interval_orders_and_floors_bounds():
    lo, hi = clip_interval(np.array([2.0, 5.0]), np.array([3.0, -1.0]), np.array([1.0, 9.0]))
    assert lo.tolist() == [2.0, 0.0]
    assert hi.tolist() == [2.0, 9.0]
