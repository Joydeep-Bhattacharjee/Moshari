"""Model selection on the walk-forward backtest (PRD Part 5.1-5.5 and 5.8).

Per horizon: M1 GLM, M2 HGB-Poisson, M3 HGB-log -> learning-rate check on the best HGB family
-> winner by mean backtest RMSE -> monotonic variant kept if RMSE worsens <= 2% -> lag ablation
-> alert decision scale -> group permutation importance. The holdout is never touched here.

Usage: python -m src.selection   (about 3 minutes; results go to models/meta.json)
"""
from __future__ import annotations

import sys
import time
from dataclasses import replace

import pandas as pd

from src import config as cfg
from src.backtest import BacktestResult, fold_frames, run_backtest, summarize
from src.baselines import BASELINES
from src.data import load_weekly
from src.eda import update_meta
from src.explain import group_permutation_importance
from src.features import target_col
from src.models import LAGGED_RAIN_COLS, LEARNING_RATES, ModelSpec, make_model
from src.split import walk_forward_folds
from src.tiers import alert_tradeoff, choose_decision_scale, fit_thresholds, pooled_tier_metrics

STAGE_ONE = (ModelSpec("glm_poisson"), ModelSpec("hgb_poisson"), ModelSpec("hgb_log"))
MONOTONIC_TOLERANCE = 0.02  # keep constraints if backtest RMSE worsens by at most 2%


def keep_monotonic(rmse_plain: float, rmse_monotonic: float, tolerance: float = MONOTONIC_TOLERANCE) -> bool:
    return rmse_monotonic <= rmse_plain * (1 + tolerance)


def lag_gain_pct(rmse_with_lags: float, rmse_without_lags: float) -> float:
    """How much lower RMSE is with lagged rain, as % of the no-lag RMSE."""
    return round(100 * (rmse_without_lags - rmse_with_lags) / rmse_without_lags, 2)


def _mean_rmse(result: BacktestResult) -> float:
    return float(result.metrics["rmse"].mean())


def _run(spec: ModelSpec, horizon: int, frames) -> BacktestResult:
    return run_backtest(lambda _h: make_model(spec), horizon, frames, spec.name)


def _search(horizon: int, frames) -> tuple[dict, ModelSpec]:
    """Stage one plus the learning-rate check; returns {name: (spec, result)} and the RMSE winner."""
    results = {s.name: (s, _run(s, horizon, frames)) for s in STAGE_ONE}
    hgb_specs = [s for s, _ in results.values() if s.family != "glm_poisson"]
    best_hgb = min(hgb_specs, key=lambda s: _mean_rmse(results[s.name][1]))
    for lr in LEARNING_RATES:
        if lr != best_hgb.learning_rate:
            spec = replace(best_hgb, learning_rate=lr)
            results[spec.name] = (spec, _run(spec, horizon, frames))
    winner = min((s for s, _ in results.values()), key=lambda s: _mean_rmse(results[s.name][1]))
    return results, winner


def _monotonic_step(winner: ModelSpec, results: dict, horizon: int, frames) -> tuple[ModelSpec, dict]:
    if winner.family == "glm_poisson":
        return winner, {"tested": False, "reason": "monotonic constraints apply to HGB only"}
    constrained = replace(winner, monotonic=True)
    results[constrained.name] = (constrained, _run(constrained, horizon, frames))
    plain, mono = _mean_rmse(results[winner.name][1]), _mean_rmse(results[constrained.name][1])
    kept = keep_monotonic(plain, mono)
    return (constrained if kept else winner), {
        "tested": True,
        "rmse_plain": round(plain, 4),
        "rmse_monotonic": round(mono, 4),
        "change_pct": round(100 * (mono - plain) / plain, 2),
        "kept": kept,
    }


def _lag_ablation(chosen: ModelSpec, chosen_rmse: float, horizon: int, frames) -> dict:
    ablated = replace(chosen, feature_set="no_lagged_rain")
    without = _mean_rmse(_run(ablated, horizon, frames))
    return {
        "model": ablated.name,
        "removed_features": list(LAGGED_RAIN_COLS),
        "rmse_with_lags": round(chosen_rmse, 4),
        "rmse_without_lags": round(without, 4),
        "lag_gain_pct": lag_gain_pct(chosen_rmse, without),
    }


def _fold_groups(result: BacktestResult, frames, horizon: int) -> list:
    """(y_true, y_pred, thresholds) per fold, thresholds learned on that fold's training targets."""
    y_col = target_col(horizon)
    groups = []
    for fold, frame in frames:
        train_y = frame.loc[frame[cfg.DATE_COL] <= fold.train_end, y_col].dropna()
        preds = result.predictions[result.predictions["fold"] == fold.number]
        groups.append((preds["y_true"].to_numpy(), preds["y_pred"].to_numpy(), fit_thresholds(train_y)))
    return groups


def _alert_policy(result: BacktestResult, frames, horizon: int) -> dict:
    groups = _fold_groups(result, frames, horizon)
    tradeoff = alert_tradeoff(groups)
    scale = choose_decision_scale(tradeoff)
    return {
        "decision_scale": scale,
        "at_scale_1": pooled_tier_metrics(groups, 1.0),
        "at_chosen_scale": pooled_tier_metrics(groups, scale),
        "tradeoff": tradeoff,
    }


def _importance(result: BacktestResult, frames, horizon: int) -> dict:
    y_col = target_col(horizon)
    per_fold = []
    for model, (fold, frame) in zip(result.models, frames):
        test = frame[frame[y_col].notna() & frame[cfg.DATE_COL].between(fold.test_start, fold.test_end)]
        per_fold.append(group_permutation_importance(model, test, test[y_col]))
    return pd.DataFrame(per_fold).mean().round(4).sort_values(ascending=False).to_dict()


def _comparison(results: dict, horizon: int, frames, chosen: ModelSpec) -> dict:
    baselines = [run_backtest(factory, horizon, frames, name).metrics for name, factory in BASELINES.items()]
    table = summarize(pd.concat([*baselines, *(r.metrics for _, r in results.values())]))
    table = table.drop(columns="horizon").sort_values("rmse", ignore_index=True)
    best = table[table["model"] == chosen.name].iloc[0]
    base = table[table["model"].isin(BASELINES)]
    beats = bool((best["rmse"] < base["rmse"]).all() and (best["mae"] < base["mae"]).all())
    return {"candidates": table.to_dict(orient="records"), "beats_baselines": beats}


def select_horizon(horizon: int, frames) -> dict:
    results, winner = _search(horizon, frames)
    chosen, monotonic = _monotonic_step(winner, results, horizon, frames)
    chosen_result = results[chosen.name][1]
    return {
        **_comparison(results, horizon, frames, chosen),
        "winner_unconstrained": winner.name,
        "monotonic": monotonic,
        "chosen": {**chosen.to_dict(), "name": chosen.name},
        "per_fold": chosen_result.metrics[["fold", "mae", "rmse", "n_test"]].round(4).to_dict(orient="records"),
        "lag_ablation": _lag_ablation(chosen, _mean_rmse(chosen_result), horizon, frames),
        "alerts": _alert_policy(chosen_result, frames, horizon),
        "group_importance": _importance(chosen_result, frames, horizon),
    }


def _print_horizon(horizon: int, result: dict) -> None:
    alerts = result["alerts"]["at_chosen_scale"]
    print(f"\n=== h={horizon}: chosen {result['chosen']['name']} (beats baselines: {result['beats_baselines']})")
    print(pd.DataFrame(result["candidates"]).to_string(index=False))
    print(f"monotonic: {result['monotonic']}")
    print(f"lag gain: {result['lag_ablation']['lag_gain_pct']}% lower RMSE with lagged rain")
    print(
        f"alerts at scale {result['alerts']['decision_scale']}: "
        f"recall={alerts['alert_recall']} precision={alerts['alert_precision']}"
    )
    print(f"group importance: {result['group_importance']}")


def main() -> int:
    start = time.perf_counter()
    weekly = load_weekly()
    frames = fold_frames(weekly, walk_forward_folds(weekly[cfg.DATE_COL]))
    selection = {}
    for horizon in cfg.HORIZONS:
        selection[str(horizon)] = select_horizon(horizon, frames)
        _print_horizon(horizon, selection[str(horizon)])
    runtime = round(time.perf_counter() - start, 1)
    update_meta({"model_selection": {"horizons": selection, "runtime_seconds": runtime}})
    print(f"\nselection done in {runtime}s; saved to {cfg.META_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
