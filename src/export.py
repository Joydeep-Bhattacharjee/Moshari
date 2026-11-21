"""Export real model output as static JSON for the React dashboard (public/data/).

The frontend reads these files directly: no server, no API calls.
Usage: python -m src.export
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src import config as cfg
from src.data import load_weekly
from src.explain import group_impacts
from src.features import FEATURE_GROUPS, build_features, target_col
from src.models import clip_interval
from src.predict import load_bundle
from src.scenario import MULTIPLIER_RANGE, scale_recent_rain_features
from src.tiers import ALERT_FROM_TIER, TIERS

OUT_DIR = cfg.ROOT / "public" / "data"
FIRST_SELECTABLE_WEEK = pd.Timestamp("2024-01-01")  # covers the 2024 and 2025 monsoons
TIMELINE_WEEKS = 26  # the timeline shows 26 earlier forecasts, so export them too
MULTIPLIERS = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
assert MULTIPLIERS[0] == MULTIPLIER_RANGE[0] and MULTIPLIERS[-1] == MULTIPLIER_RANGE[1]


def _round(values, digits: int = 2) -> list:
    return [None if pd.isna(v) else round(float(v), digits) for v in values]


def _predict(models: dict, rows: pd.DataFrame) -> dict:
    pred = models["point"].predict(rows)
    lo, hi = clip_interval(pred, models["q10"].predict(rows), models["q90"].predict(rows))
    return {"pred": pred, "lo": lo, "hi": hi}


def _horizon_block(frame: pd.DataFrame, bundle: dict, horizon: int, weeks: list) -> dict:
    """Per ward: arrays aligned to `weeks` for baseline, drivers, actuals and every rain scenario."""
    models = bundle["models"][horizon]
    rows = frame[frame[cfg.DATE_COL].isin(weeks)].sort_values([cfg.WARD_COL, cfg.DATE_COL])
    base = _predict(models, rows)
    impacts = group_impacts(models["point"], rows, bundle["train_medians"])[list(FEATURE_GROUPS)]
    scenarios = {
        m: _predict(models, scale_recent_rain_features(rows, m, bundle["feature_params"]))
        for m in MULTIPLIERS if m != 1.0
    }
    block = {}
    for ward, idx in rows.groupby(cfg.WARD_COL).indices.items():
        block[ward] = {
            **{key: _round(values[idx], 2) for key, values in base.items()},
            "actual": _round(rows[target_col(horizon)].to_numpy()[idx], 0),
            "drivers": [_round(r, 2) for r in impacts.to_numpy()[idx]],
            "scenario": {
                f"{m:g}": {key: _round(values[idx], 2) for key, values in result.items()}
                for m, result in scenarios.items()
            },
        }
    return block


def _wards(weekly: pd.DataFrame) -> list[dict]:
    first = weekly.drop_duplicates(cfg.WARD_COL).sort_values(cfg.WARD_COL)
    return [
        {
            "id": row[cfg.WARD_COL],
            "city": row[cfg.CITY_COL],
            "waterlogging": round(float(row[cfg.WATERLOG_COL]), 2),
            "density": int(row[cfg.DENSITY_COL]),
            "sanitation": round(float(row[cfg.SANITATION_COL]), 2),
        }
        for _, row in first.iterrows()
    ]


def _history(weekly: pd.DataFrame) -> dict:
    ordered = weekly.sort_values([cfg.WARD_COL, cfg.DATE_COL])
    weeks = sorted(ordered[cfg.DATE_COL].unique())
    by_ward = ordered.groupby(cfg.WARD_COL)
    return {
        "weeks": [pd.Timestamp(w).date().isoformat() for w in weeks],
        "rain": {ward: _round(g[cfg.RAIN_COL], 1) for ward, g in by_ward},
        "cases": {ward: _round(g[cfg.TARGET_COL], 0) for ward, g in by_ward},
    }


def build_dashboard(weekly: pd.DataFrame, bundle: dict, meta: dict) -> dict:
    frame = build_features(weekly, bundle["feature_params"])
    last = frame[cfg.DATE_COL].max()
    start = FIRST_SELECTABLE_WEEK - pd.Timedelta(weeks=TIMELINE_WEEKS)
    weeks = sorted(d for d in frame[cfg.DATE_COL].unique() if start <= d <= last)
    info = meta["model_info"]
    model_keys = ("trained_at", "train_start", "train_end", "holdout_start", "holdout_end", "sklearn_version")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": {key: info[key] for key in model_keys},
        "tiers": list(TIERS),
        "thresholds": {str(h): list(t) for h, t in bundle["thresholds"].items()},
        "decision_scale": {str(h): s for h, s in bundle["decision_scale"].items()},
        "weeks": [pd.Timestamp(w).date().isoformat() for w in weeks],
        "first_selectable_week": FIRST_SELECTABLE_WEEK.date().isoformat(),
        "multipliers": list(MULTIPLIERS),
        "driver_groups": list(FEATURE_GROUPS),
        "wards": _wards(weekly),
        "history": _history(weekly),
        "forecasts": {str(h): _horizon_block(frame, bundle, h, weeks) for h in cfg.HORIZONS},
    }


def alert_counts(confusion: list[list[int]]) -> dict:
    """Collapse the 4x4 tier confusion matrix (rows true, cols predicted) to alert vs no alert."""
    matrix = np.asarray(confusion)
    a = ALERT_FROM_TIER
    return {
        "tn": int(matrix[:a, :a].sum()),
        "fp": int(matrix[:a, a:].sum()),
        "fn": int(matrix[a:, :a].sum()),
        "tp": int(matrix[a:, a:].sum()),
    }


def build_validation(meta: dict) -> dict:
    horizons = {}
    for h, selection in meta["model_selection"]["horizons"].items():
        holdout = meta["holdout"][h]
        horizons[h] = {
            "model": selection["chosen"]["name"],
            "per_fold": selection["per_fold"],
            "holdout": {
                "model": holdout["model"],
                "baselines": holdout["baselines"],
                "beats_baselines": holdout["beats_baselines"],
                "coverage_80": holdout["coverage_80"],
                "coverage_80_nonzero_weeks": holdout["coverage_80_nonzero_weeks"],
                "alert_recall": holdout["tiers"]["alert_recall"],
                "alert_precision": holdout["tiers"]["alert_precision"],
                **alert_counts(holdout["tiers"]["confusion_matrix"]),
            },
            "lag_gain_pct": selection["lag_ablation"]["lag_gain_pct"],
            "group_importance": selection["group_importance"],
        }
    return {
        "split": meta["split"],
        "lag_correlation": meta["lag_correlation"],
        "horizons": horizons,
        "test_series": meta["test_series"],
    }


def _write(path: Path, payload: dict) -> float:
    path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    return path.stat().st_size / 1e6


def main() -> int:
    bundle = load_bundle()
    meta = json.loads(cfg.META_PATH.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dashboard_mb = _write(OUT_DIR / "dashboard.json", build_dashboard(load_weekly(), bundle, meta))
    validation_mb = _write(OUT_DIR / "validation.json", build_validation(meta))
    print(f"wrote {OUT_DIR}: dashboard.json {dashboard_mb:.2f} MB, validation.json {validation_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
