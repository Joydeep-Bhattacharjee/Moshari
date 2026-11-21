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
