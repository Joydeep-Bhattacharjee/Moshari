"""Phase 2 data for the React dashboard: python -m src.ops.ui_export

public/data/ops/config.json     constants (read from the Python modules), drainage
                                coefficients, wards with static attributes and capacity
public/data/ops/forecasts.json  4-week forecast window for every selectable as-of week,
                                plus each ward's recent rain for the crew effect

Forecasts are written at full float precision, so the browser recomputes demand,
allocation and routing from exactly the numbers Python uses. The crew effect in the
browser is the closed form of the Poisson GLM, ratio = exp(-(b_wl + b_int * rain) * d_wl),
which tests/test_ui_export.py checks against re-running the model. forecasts.json is
also the cached level of the forecast fallback chain.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

from src import config as cfg
from src.explain import GROUP_LABELS
from src.ops import allocate, crews, demand, overflow, scenario, simulate
from src.ops.capacity import CAPACITY_SOURCE
from src.ops.export_pack import current_commit
from src.ops.forecast_window import MAX_WINDOW_WEEKS, WINDOW_PLAN, forecast_window
from src.ops.pipeline import Context, load_context
from src.predict import rows_for, valid_dates
from src.tiers import TIERS

OUT_DIR = cfg.ROOT / "public" / "data" / "ops"
FIRST_ASOF = "2024-01-01"  # covers the 2024 and 2025 monsoons, like the Phase 1 picker
RAIN_ORIGIN_HORIZON = 2  # any horizon works: the as-of rows are the same
DRIVER_LABELS = sorted(set(GROUP_LABELS.values()) | {"none"})


def closed_form_ratio(coef: dict, rain_sum: float, waterlog: float, waterlog_after: float) -> float:
    """Crew effect of the Poisson GLM: exp(-(b_wl + b_int * rain) * (wl - wl'))."""
    return math.exp(-(coef["waterlog"] + coef["rain_x_waterlog"] * rain_sum) * (waterlog - waterlog_after))


def _constants(bundle: dict) -> dict:
    return {
        "tiers": list(TIERS),
        "thresholds": {str(h): list(t) for h, t in bundle["thresholds"].items()},
        "decision_scale": {str(h): s for h, s in bundle["decision_scale"].items()},
        "window_plan": {str(k): list(v) for k, v in WINDOW_PLAN.items()},
        "max_window_weeks": MAX_WINDOW_WEEKS,
        "supply_per_1000": dict(cfg.SUPPLY_PER_1000_CASES),
        "confidence_cols": dict(demand.CONFIDENCE_COLS),
        "risk_norm": list(allocate.RISK_NORM),
        "weights": {"risk": allocate.RISK_WEIGHT, "density": allocate.DENSITY_WEIGHT, "cases": allocate.CASES_WEIGHT},
        "stock_pct_range": list(allocate.STOCK_PCT_RANGE),
        "critical_fill": allocate.CRITICAL_FILL,
        "high_risk_fill": allocate.HIGH_RISK_FILL,
        "high_risk_from": allocate.HIGH_RISK_FROM,
        "crews_by_tier": list(crews.CREWS_BY_TIER),
        "poor_drainage_from": crews.POOR_DRAINAGE_FROM,
        "buffer_pct": overflow.BUFFER_PCT,
        "bands": dict(simulate.BANDS),
        "crew_saturation": simulate.CREW_SATURATION,
        "max_crews_per_ward": simulate.MAX_CREWS_PER_WARD,
        "ramp_by_week": {str(k): v for k, v in simulate.RAMP_BY_WEEK.items()},
        "waterlog_floor": simulate.WATERLOG_FLOOR,
        "effect_horizon_by_week": {str(k): v for k, v in simulate.EFFECT_HORIZON_BY_WEEK.items()},
        "defaults": {
            "asof": scenario.DEFAULT_ASOF,
            "weeks": scenario.DEFAULT_WINDOW_WEEKS,
            "stock_pct": allocate.DEFAULT_STOCK_PCT,
            "floor_pct": allocate.DEFAULT_FLOOR_PCT,
            "confidence": demand.DEFAULT_CONFIDENCE,
            "crews_total": scenario.DEFAULT_CREWS_TOTAL,
            "crew_mode": "priority",
            "band": simulate.DEFAULT_BAND,
            "apply_intervention": True,
        },
    }


def build_config(ctx: Context) -> dict:
    capacity = ctx.capacity.set_index(cfg.WARD_COL)["capacity"]
    wards = [
        {
            "id": w[cfg.WARD_COL],
            "city": w[cfg.CITY_COL],
            "density": float(w[cfg.DENSITY_COL]),
            "waterlog": float(w[cfg.WATERLOG_COL]),
            "sanitation": float(w[cfg.SANITATION_COL]),
            "capacity": int(capacity[w[cfg.WARD_COL]]),
        }
        for w in ctx.wards.to_dict(orient="records")
    ]
    return {
        "provenance": {
            "data_hash": ctx.data_hash,
            "git_commit": ctx.git_commit,
            "model_trained_at": ctx.bundle["trained_at"],
            "train_end": ctx.bundle["train_end"],
            "capacity_source": CAPACITY_SOURCE,
        },
        "constants": _constants(ctx.bundle),
        "drainage": {str(h): c for h, c in simulate.drainage_coefficients(ctx.bundle).items()},
        "driver_labels": DRIVER_LABELS,
        "wards": wards,
    }


def _asof_weeks(frame: pd.DataFrame) -> list[pd.Timestamp]:
    return [d for d in valid_dates(frame)[1:] if d >= pd.Timestamp(FIRST_ASOF)]


def _window_block(ctx: Context, asof: pd.Timestamp) -> dict:
    window = forecast_window(ctx.frame, ctx.bundle, asof, MAX_WINDOW_WEEKS)
    rain = rows_for(ctx.frame, ctx.bundle, asof, RAIN_ORIGIN_HORIZON).set_index(cfg.WARD_COL)[simulate.RAIN_SUM_COL]
    index = {label: i for i, label in enumerate(DRIVER_LABELS)}
    return {
        ward: {
            "expected": rows["expected_cases"].tolist(),
            "p10": rows["p10_cases"].tolist(),
            "p90": rows["p90_cases"].tolist(),
            "tier_rank": rows["tier_rank"].astype(int).tolist(),
            "actual": [None if pd.isna(a) else float(a) for a in rows["actual_cases"]],
            "top_driver": [index[d] for d in rows["top_driver"]],
            "rain_sum": float(rain[ward]),
        }
        for ward, rows in window.groupby(cfg.WARD_COL, sort=True)
    }


def build_forecasts(ctx: Context) -> dict:
    weeks = _asof_weeks(ctx.frame)
    return {
        "asof_weeks": [w.date().isoformat() for w in weeks],
        "driver_labels": DRIVER_LABELS,
        "windows": {w.date().isoformat(): _window_block(ctx, w) for w in weeks},
    }


def _write(path: Path, payload: dict) -> float:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    return path.stat().st_size / 1e6


def main() -> int:
    ctx = load_context(git_commit=current_commit())
    config_mb = _write(OUT_DIR / "config.json", build_config(ctx))
    forecasts_mb = _write(OUT_DIR / "forecasts.json", build_forecasts(ctx))
    print(f"wrote {OUT_DIR}: config.json {config_mb:.2f} MB, forecasts.json {forecasts_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
