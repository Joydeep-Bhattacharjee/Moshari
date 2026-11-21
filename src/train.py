"""Final fit on all pre-holdout weeks, one holdout evaluation, and the model bundle (PRD 5.5-5.7).

Reads the chosen model per horizon from models/meta.json (written by `python -m src.selection`).
Usage: python -m src.train   (under a minute)
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn

from src import config as cfg
from src.backtest import error_metrics
from src.baselines import BASELINES, add_seasonal_reference
from src.data import load_weekly
from src.eda import update_meta
from src.features import FEATURE_COLS, FEATURE_GROUPS, build_features, fit_feature_params, target_col
from src.models import MONOTONIC, QUANTILES, ModelSpec, clip_interval, make_model
from src.split import holdout_split
from src.tiers import TIERS, fit_thresholds, tier_metrics


def load_selection(path=cfg.META_PATH) -> dict:
    """{horizon: {"spec": ModelSpec, "decision_scale": float}} from the selection step."""
    meta = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    horizons = meta.get("model_selection", {}).get("horizons")
    if not horizons:
        raise RuntimeError("no model selection in meta.json - run `python -m src.selection` first")
    fields = ("family", "learning_rate", "monotonic", "feature_set")
    return {
        int(h): {
            "spec": ModelSpec(**{k: result["chosen"][k] for k in fields}),
            "decision_scale": float(result["alerts"]["decision_scale"]),
        }
        for h, result in horizons.items()
    }


def _data_hash(path=cfg.RAW_DATA_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _fit_horizon(spec: ModelSpec, train: pd.DataFrame, y_col: str) -> dict:
    y = train[y_col]
    return {
        "point": make_model(spec).fit(train, y),
        "q10": make_model(spec, quantile=QUANTILES[0]).fit(train, y),
        "q90": make_model(spec, quantile=QUANTILES[1]).fit(train, y),
    }


def _rounded(errors: dict) -> dict:
    return {k: round(v, 4) for k, v in errors.items()}


def _evaluate_holdout(models: dict, train: pd.DataFrame, holdout: pd.DataFrame, horizon: int, thresholds, scale: float):
    """Score the holdout once: errors vs baselines, interval coverage, tier and alert metrics."""
    y_col = target_col(horizon)
    y = holdout[y_col].to_numpy(dtype=float)
    pred = models["point"].predict(holdout)
    lo, hi = clip_interval(pred, models["q10"].predict(holdout), models["q90"].predict(holdout))
    baselines = {
        name: error_metrics(y, factory(horizon).fit(train, train[y_col]).predict(holdout))
        for name, factory in BASELINES.items()
    }
    errors = error_metrics(y, pred)
    inside = (y >= lo) & (y <= hi)
    report = {
        "n": int(y.size),
        "model": _rounded(errors),
        "baselines": {name: _rounded(e) for name, e in baselines.items()},
        "beats_baselines": all(errors["rmse"] < b["rmse"] and errors["mae"] < b["mae"] for b in baselines.values()),
        "coverage_80": round(float(np.mean(inside)), 4),
        "coverage_80_nonzero_weeks": round(float(np.mean(inside[y > 0])), 4),  # zeros are easy to cover
        "mean_interval_width": round(float(np.mean(hi - lo)), 3),
        "tiers": tier_metrics(y, pred, thresholds, scale),
    }
    series = holdout[[cfg.WARD_COL, cfg.DATE_COL]].assign(y_true=y, pred=pred, lo=lo, hi=hi)
    return report, series


def _compact_series(series: pd.DataFrame) -> dict:
    """Holdout series per ward, aligned to one date list (keeps meta.json small)."""
    dates = sorted(series[cfg.DATE_COL].unique())
    wards = {}
    for ward, group in series.groupby(cfg.WARD_COL):
        aligned = group.set_index(cfg.DATE_COL).reindex(dates)
        wards[ward] = {
            col: [None if pd.isna(v) else round(float(v), 2) for v in aligned[col]]
            for col in ("y_true", "pred", "lo", "hi")
        }
    return {"dates": [pd.Timestamp(d).date().isoformat() for d in dates], "wards": wards}


def _bundle(models: dict, selection: dict, thresholds: dict, params: dict, pre_holdout: pd.DataFrame, split) -> dict:
    return {
        "models": models,
        "specs": {h: selection[h]["spec"].to_dict() for h in models},
        "feature_cols": FEATURE_COLS,
        "feature_groups": FEATURE_GROUPS,
        "feature_params": params,
        "thresholds": thresholds,
        "decision_scale": {h: selection[h]["decision_scale"] for h in models},
        "tiers": TIERS,
        "train_medians": pre_holdout[list(FEATURE_COLS)].median().round(4).to_dict(),
        "monotonic_cfg": MONOTONIC,
        "sklearn_version": sklearn.__version__,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_hash": _data_hash(),
        "train_end": split.train_end.date().isoformat(),
        "holdout_start": split.holdout_start.date().isoformat(),
    }


def _model_info(bundle: dict, runtime: float, frame: pd.DataFrame) -> dict:
    keys = ("sklearn_version", "trained_at", "data_hash", "train_end", "holdout_start", "specs", "decision_scale")
    return {
        **{key: bundle[key] for key in keys},
        "thresholds": {h: [round(t, 2) for t in thr] for h, thr in bundle["thresholds"].items()},
        "train_start": frame[cfg.DATE_COL].min().date().isoformat(),
        "holdout_end": frame[cfg.DATE_COL].max().date().isoformat(),
        "bundle_mb": round(cfg.MODEL_PATH.stat().st_size / 1e6, 2),
        "train_seconds": runtime,
    }


def main() -> int:
    start = time.perf_counter()
    selection = load_selection()
    weekly = load_weekly()
    split = holdout_split(weekly[cfg.DATE_COL])
    params = fit_feature_params(weekly, split.train_end)
    frame = add_seasonal_reference(build_features(weekly, params))
    models, thresholds, reports, series = {}, {}, {}, {}
    for h in cfg.HORIZONS:
        y_col = target_col(h)
        known = frame[y_col].notna()
        train = frame[known & (frame[cfg.DATE_COL] <= split.train_end)]
        holdout = frame[known & (frame[cfg.DATE_COL] >= split.holdout_start)]
        models[h] = _fit_horizon(selection[h]["spec"], train, y_col)
        thresholds[h] = fit_thresholds(train[y_col])
        report, test_series = _evaluate_holdout(
            models[h], train, holdout, h, thresholds[h], selection[h]["decision_scale"]
        )
        reports[str(h)], series[str(h)] = report, _compact_series(test_series)
        print(f"h={h}: holdout {report['model']}, beats baselines: {report['beats_baselines']}")
    bundle = _bundle(models, selection, thresholds, params, frame[frame[cfg.DATE_COL] <= split.train_end], split)
    joblib.dump(bundle, cfg.MODEL_PATH, compress=3)
    runtime = round(time.perf_counter() - start, 1)
    info = _model_info(bundle, runtime, frame)
    update_meta({"holdout": reports, "test_series": series, "model_info": info})
    print(f"saved {cfg.MODEL_PATH} ({info['bundle_mb']} MB) in {runtime}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
