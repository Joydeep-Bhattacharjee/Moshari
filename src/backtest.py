"""Walk-forward backtest (PRD section 6.4): MAE/RMSE per fold and horizon.

Features are rebuilt per fold so learned thresholds only see that fold's training weeks.
Usage: python -m src.backtest   (prints and saves the baseline table)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from src import config as cfg
from src.baselines import BASELINES, add_seasonal_reference
from src.data import load_weekly
from src.eda import update_meta
from src.features import build_features, fit_feature_params, target_col
from src.split import Fold, holdout_split, walk_forward_folds

ModelFactory = Callable[[int], object]  # horizon -> unfitted model with fit/predict


@dataclass(frozen=True)
class BacktestResult:
    metrics: pd.DataFrame  # one row per fold
    predictions: pd.DataFrame  # one row per test (ward, origin week)
    models: tuple = ()  # fitted model per fold, same order as the folds


def fold_frames(weekly: pd.DataFrame, folds: tuple[Fold, ...]) -> tuple[tuple[Fold, pd.DataFrame], ...]:
    """Feature table per fold, with thresholds fit on that fold's training weeks only."""
    return tuple(
        (fold, add_seasonal_reference(build_features(weekly, fit_feature_params(weekly, fold.train_end))))
        for fold in folds
    )


def error_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    diff = y_pred - y_true
    return {"mae": float(np.mean(np.abs(diff))), "rmse": float(np.sqrt(np.mean(diff**2)))}


def _evaluate_fold(model_factory: ModelFactory, horizon: int, fold: Fold, frame: pd.DataFrame):
    y_col = target_col(horizon)
    known = frame[y_col].notna()
    train = frame[known & (frame[cfg.DATE_COL] <= fold.train_end)]
    test = frame[known & frame[cfg.DATE_COL].between(fold.test_start, fold.test_end)]
    model = model_factory(horizon).fit(train, train[y_col])
    y_pred = np.asarray(model.predict(test), dtype=float)
    metrics = {
        "fold": fold.number,
        "train_end": fold.train_end.date().isoformat(),
        "test_start": fold.test_start.date().isoformat(),
        "test_end": fold.test_end.date().isoformat(),
        "n_train": len(train),
        "n_test": len(test),
        **error_metrics(test[y_col].to_numpy(dtype=float), y_pred),
    }
    predictions = test[[cfg.WARD_COL, cfg.DATE_COL]].assign(
        fold=fold.number, y_true=test[y_col].to_numpy(), y_pred=y_pred
    )
    return metrics, predictions, model


def run_backtest(model_factory: ModelFactory, horizon: int, frames, name: str = "model") -> BacktestResult:
    """Fit a fresh model per fold on its training weeks; score it on that fold's test block."""
    results = [_evaluate_fold(model_factory, horizon, fold, frame) for fold, frame in frames]
    metrics = pd.DataFrame([m for m, _, _ in results]).assign(model=name, horizon=horizon)
    predictions = pd.concat([p for _, p, _ in results], ignore_index=True).assign(
        model=name, horizon=horizon
    )
    return BacktestResult(metrics=metrics, predictions=predictions, models=tuple(m for _, _, m in results))


def summarize(metrics: pd.DataFrame) -> pd.DataFrame:
    """Mean MAE/RMSE across folds per model and horizon."""
    return metrics.groupby(["model", "horizon"], as_index=False)[["mae", "rmse"]].mean().round(4)


def _split_meta(weekly: pd.DataFrame, folds: tuple[Fold, ...]) -> dict:
    split = holdout_split(weekly[cfg.DATE_COL])
    return {
        "data_start": weekly[cfg.DATE_COL].min().date().isoformat(),
        "data_end": weekly[cfg.DATE_COL].max().date().isoformat(),
        "holdout_train_end": split.train_end.date().isoformat(),
        "holdout_start": split.holdout_start.date().isoformat(),
        "purge_gap_weeks": cfg.PURGE_GAP_WEEKS,
        "folds": [
            {"fold": f.number, "train_end": f.train_end.date().isoformat(),
             "test_start": f.test_start.date().isoformat(), "test_end": f.test_end.date().isoformat()}
            for f in folds
        ],
    }


def main() -> int:
    weekly = load_weekly()
    folds = walk_forward_folds(weekly[cfg.DATE_COL])
    frames = fold_frames(weekly, folds)
    metrics = pd.concat(
        [run_backtest(factory, h, frames, name).metrics
         for name, factory in BASELINES.items() for h in cfg.HORIZONS],
        ignore_index=True,
    )
    summary = summarize(metrics)
    update_meta({
        "split": _split_meta(weekly, folds),
        "backtest_baselines": {
            "per_fold": metrics.round(4).to_dict(orient="records"),
            "mean": summary.to_dict(orient="records"),
        },
    })
    print(metrics[["model", "horizon", "fold", "test_start", "test_end", "mae", "rmse"]].round(3).to_string(index=False))
    print("\nMean over folds:\n" + summary.to_string(index=False))
    print(f"\nsaved to {cfg.META_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
