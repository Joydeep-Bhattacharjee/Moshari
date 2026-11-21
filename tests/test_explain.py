import numpy as np
import pandas as pd

from src.explain import group_permutation_importance


class UsesRainOnly:
    feature_cols = ("rain_lag_0", "temp_lag_0")

    def predict(self, frame):
        return frame["rain_lag_0"].to_numpy()


def test_group_importance_ranks_used_group_above_ignored_one():
    rng = np.random.default_rng(0)
    frame = pd.DataFrame({"rain_lag_0": rng.gamma(2, 10, 200), "temp_lag_0": rng.normal(28, 2, 200)})
    importance = group_permutation_importance(UsesRainOnly(), frame, frame["rain_lag_0"])
    assert set(importance) == {"rain", "temperature"}  # groups without used features are skipped
    assert importance["rain"] > 0
    assert importance["temperature"] == 0


def test_group_importance_does_not_modify_frame():
    frame = pd.DataFrame({"rain_lag_0": [1.0, 2.0, 3.0], "temp_lag_0": [25.0, 26.0, 27.0]})
    snapshot = frame.copy()
    group_permutation_importance(UsesRainOnly(), frame, frame["rain_lag_0"])
    pd.testing.assert_frame_equal(frame, snapshot)


# --- local drivers -------------------------------------------------------------
from src.explain import driver_sentence, group_impacts  # noqa: E402


class AdditiveModel:
    feature_cols = ("rain_lag_0", "temp_lag_0")

    def predict(self, frame):
        return 2.0 * frame["rain_lag_0"].to_numpy() + 1.0 * frame["temp_lag_0"].to_numpy()


def test_group_impact_is_change_from_training_median():
    rows = pd.DataFrame({"rain_lag_0": [10.0, 0.0], "temp_lag_0": [30.0, 30.0]})
    impacts = group_impacts(AdditiveModel(), rows, {"rain_lag_0": 5.0, "temp_lag_0": 28.0})
    assert impacts["rain"].tolist() == [10.0, -10.0]  # 2 * (value - median)
    assert impacts["temperature"].tolist() == [2.0, 2.0]
    assert set(impacts.columns) == {"rain", "temperature"}


def test_sentence_names_top_raising_drivers():
    impacts = pd.Series({"rain": 3.0, "ward": 1.0, "season": -2.0})
    sentence = driver_sentence("High", 3, impacts)
    assert sentence == (
        "High risk in 3 weeks, mainly driven by heavy rain in recent weeks "
        "and poor drainage, crowding or sanitation in this ward."
    )


def test_sentence_explains_low_risk_by_lowering_drivers():
    impacts = pd.Series({"rain": -1.0, "season": -3.0, "ward": 0.01})
    assert driver_sentence("Low", 2, impacts) == (
        "Low risk in 2 weeks, kept down by the time of year (dry season) and little recent rain."
    )
