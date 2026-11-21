"""Explainability without SHAP (PRD section 6.8).

Local: grouped ablation. Set one feature group to its training median, re-predict; the change in
predicted cases is that group's signed impact. Global: permutation importance by feature group.
Working on whole groups keeps correlated features (e.g. rain lags) from hiding each other.
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


MIN_IMPACT_CASES = 0.05  # impacts smaller than this are treated as no effect

GROUP_LABELS = {
    "rain": "recent rain",
    "temperature": "temperature",
    "humidity": "humidity",
    "ward": "ward vulnerability",
    "interactions": "rain x vulnerability",
    "season": "season",
}
# (phrase when the group raises risk, phrase when it lowers risk)
GROUP_PHRASES = {
    "rain": ("heavy rain in recent weeks", "little recent rain"),
    "temperature": ("mosquito-friendly temperatures", "temperatures outside the mosquito range"),
    "humidity": ("high humidity", "low humidity"),
    "ward": ("poor drainage, crowding or sanitation in this ward", "good drainage and sanitation in this ward"),
    "interactions": ("recent rain falling on a vulnerable ward", "little rain on vulnerable areas"),
    "season": ("the time of year (monsoon season)", "the time of year (dry season)"),
}


def group_impacts(model, rows: pd.DataFrame, medians: dict) -> pd.DataFrame:
    """Signed impact (cases) per feature group per row: prediction minus prediction with that
    group set to its training median. Positive = the group pushes risk up."""
    base = model.predict(rows)
    impacts = {}
    for group, cols in FEATURE_GROUPS.items():
        used = [c for c in cols if c in model.feature_cols]
        if used:
            neutral = rows.assign(**{c: medians[c] for c in used})
            impacts[group] = base - model.predict(neutral)
    return pd.DataFrame(impacts, index=rows.index)


def driver_sentence(tier: str, horizon: int, impacts: pd.Series, top_n: int = 2) -> str:
    """Plain-language reason, e.g. 'High risk in 3 weeks, mainly driven by heavy rain ...'."""
    raising = impacts[impacts > MIN_IMPACT_CASES].sort_values(ascending=False).head(top_n)
    if not raising.empty:
        reasons = " and ".join(GROUP_PHRASES[g][0] for g in raising.index)
        return f"{tier} risk in {horizon} weeks, mainly driven by {reasons}."
    lowering = impacts.sort_values().head(top_n)
    reasons = " and ".join(GROUP_PHRASES[g][1] for g in lowering.index)
    return f"{tier} risk in {horizon} weeks, kept down by {reasons}."
