"""Candidate models (PRD section 6.5) behind the fit(frame, y) / predict(frame) protocol."""
from __future__ import annotations

import os
import sys

# On Windows 11 loky cannot count physical cores (wmic was removed) and prints a warning plus a
# traceback the first time sklearn asks. A worker cap below the logical-core count skips that
# lookup; half the logical cores matches the physical cores on hyper-threaded CPUs.
if sys.platform == "win32" and "LOKY_MAX_CPU_COUNT" not in os.environ:
    os.environ["LOKY_MAX_CPU_COUNT"] = str(max(1, (os.cpu_count() or 2) // 2))

from dataclasses import asdict, dataclass  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import PoissonRegressor  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from src import config as cfg  # noqa: E402
from src.features import FEATURE_COLS, FEATURE_GROUPS  # noqa: E402

HGB_PARAMS = {
    "max_iter": 400,
    "max_leaf_nodes": 31,
    "min_samples_leaf": 20,
    "l2_regularization": 1.0,
    "early_stopping": False,
    "random_state": 42,
}
LEARNING_RATES = (0.03, 0.05, 0.1)
DEFAULT_LEARNING_RATE = 0.05
GLM_ALPHA = 0.01
QUANTILES = (0.1, 0.9)  # 80% prediction interval

# Directions confirmed in docs/data_audit.md: more rain / worse drainage -> more cases;
# better sanitation -> fewer cases.
MONOTONIC = {"rain_sum_lag2_4": 1, cfg.WATERLOG_COL: 1, cfg.SANITATION_COL: -1}

# Lag ablation: drop every feature built from rain in weeks t-1..t-8; keep this week's rain.
LAGGED_RAIN_COLS = (
    *(c for c in FEATURE_GROUPS["rain"] if c != "rain_lag_0"),
    *FEATURE_GROUPS["interactions"],
)
FEATURE_SETS = {
    "all": FEATURE_COLS,
    "no_lagged_rain": tuple(c for c in FEATURE_COLS if c not in LAGGED_RAIN_COLS),
}


@dataclass(frozen=True)
class ModelSpec:
    family: str  # "glm_poisson" | "hgb_poisson" | "hgb_log"
    learning_rate: float = DEFAULT_LEARNING_RATE
    monotonic: bool = False
    feature_set: str = "all"

    @property
    def name(self) -> str:
        if self.family == "glm_poisson":
            base = "M1_glm_poisson"
        else:
            label = "M2_hgb_poisson" if self.family == "hgb_poisson" else "M3_hgb_log"
            base = f"{label}_lr{self.learning_rate:g}"
        mono = "_mono" if self.monotonic else ""
        subset = "" if self.feature_set == "all" else f"_{self.feature_set}"
        return base + mono + subset

    def to_dict(self) -> dict:
        return asdict(self)


class FeatureModel:
    """Selects its feature columns from the frame; optional log1p target; never predicts < 0."""

    def __init__(self, estimator, feature_cols: tuple[str, ...], log_target: bool = False):
        self.estimator = estimator
        self.feature_cols = tuple(feature_cols)
        self.log_target = log_target

    def fit(self, frame: pd.DataFrame, y: pd.Series) -> "FeatureModel":
        target = np.log1p(y) if self.log_target else y
        self.estimator.fit(frame[list(self.feature_cols)], target)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        pred = self.estimator.predict(frame[list(self.feature_cols)])
        return np.clip(np.expm1(pred) if self.log_target else pred, 0, None)


def _hgb(spec: ModelSpec, cols: tuple[str, ...], loss: str, quantile: float | None):
    params = {**HGB_PARAMS, "learning_rate": spec.learning_rate, "loss": loss}
    if quantile is not None:
        params["quantile"] = quantile
    if spec.monotonic:
        params["monotonic_cst"] = [MONOTONIC.get(c, 0) for c in cols]
    return HistGradientBoostingRegressor(**params)


def make_model(spec: ModelSpec, quantile: float | None = None) -> FeatureModel:
    """Unfitted model for a spec. With `quantile`, an HGB quantile model using the spec's settings."""
    cols = FEATURE_SETS[spec.feature_set]
    if quantile is not None:
        return FeatureModel(_hgb(spec, cols, "quantile", quantile), cols)
    if spec.family == "glm_poisson":
        glm = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            PoissonRegressor(alpha=GLM_ALPHA, max_iter=1000),
        )
        return FeatureModel(glm, cols)
    if spec.family == "hgb_poisson":
        return FeatureModel(_hgb(spec, cols, "poisson", None), cols)
    if spec.family == "hgb_log":
        return FeatureModel(_hgb(spec, cols, "squared_error", None), cols, log_target=True)
    raise ValueError(f"unknown model family: {spec.family}")


def clip_interval(pred: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Force 0 <= lo <= pred <= hi."""
    return np.clip(np.minimum(lo, pred), 0, None), np.maximum(hi, pred)
