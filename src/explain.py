"""Explainability without SHAP (PRD section 6.8).

Global: permutation importance by feature group. Shuffling a whole group at once keeps
correlated features (e.g. rain lags) from hiding each other's importance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features import FEATURE_GROUPS


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_pred) - np.asarray(y_true)) ** 2)))


def group_permutation_importance(
    model, frame: pd.DataFrame, y: pd.Series, n_repeats: int = 3, seed: int = 42
) -> dict[str, float]:
    """RMSE increase when one feature group is shuffled across rows (mean over repeats).

    Groups the model does not use are skipped. Larger = the model relies on it more.
    """
    rng = np.random.default_rng(seed)
    y_true = y.to_numpy(dtype=float)
    base = _rmse(y_true, model.predict(frame))
    importance = {}
    for group, cols in FEATURE_GROUPS.items():
        used = [c for c in cols if c in model.feature_cols]
        if not used:
            continue
        increases = []
        for _ in range(n_repeats):
            order = rng.permutation(len(frame))
            shuffled = frame.assign(**{c: frame[c].to_numpy()[order] for c in used})
            increases.append(_rmse(y_true, model.predict(shuffled)) - base)
        importance[group] = round(float(np.mean(increases)), 4)
    return importance
