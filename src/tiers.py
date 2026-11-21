"""Risk tiers and alert metrics (PRD section 6.6).

Thresholds are quantiles of positive training targets (P50 / P75 / P90):
Low < P50 <= Medium < P75 <= High < P90 <= Critical. An alert is High or Critical.
"""
from __future__ import annotations

import numpy as np

TIERS = ("Low", "Medium", "High", "Critical")
TIER_QUANTILES = (0.50, 0.75, 0.90)
ALERT_FROM_TIER = 2  # index of "High"
MIN_ALERT_RECALL = 0.70  # PRD target: missing an outbreak costs more than a false alarm
DECISION_SCALES = tuple(round(1.0 - 0.05 * i, 2) for i in range(11))  # 1.00 down to 0.50


def fit_thresholds(y) -> tuple[float, float, float]:
    """P50/P75/P90 of positive training targets; must be strictly increasing."""
    values = np.asarray(y, dtype=float)
    positive = values[values > 0]
    if positive.size == 0:
        raise ValueError("no positive targets to learn tier thresholds from")
    thresholds = tuple(float(np.quantile(positive, q)) for q in TIER_QUANTILES)
    if not thresholds[0] < thresholds[1] < thresholds[2]:
        raise ValueError(f"tier thresholds not strictly increasing: {thresholds}")
    return thresholds


def assign_tiers(values, thresholds) -> np.ndarray:
    """Tier index 0..3 per value (index into TIERS)."""
    edges = np.asarray(thresholds, dtype=float)
    return np.searchsorted(edges, np.asarray(values, dtype=float), side="right")


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def tier_metrics(y_true, y_pred, thresholds, decision_scale: float = 1.0) -> dict:
    """Tier accuracy, alert recall/precision and confusion matrix (rows = true, cols = predicted).

    Truth is tiered with `thresholds`; predictions with thresholds * decision_scale, so a
    scale below 1 raises alerts earlier (higher recall, lower precision).
    """
    true_tier = assign_tiers(y_true, thresholds)
    pred_tier = assign_tiers(y_pred, np.asarray(thresholds) * decision_scale)
    true_alert = true_tier >= ALERT_FROM_TIER
    pred_alert = pred_tier >= ALERT_FROM_TIER
    hits = int((true_alert & pred_alert).sum())
    confusion = np.zeros((len(TIERS), len(TIERS)), dtype=int)
    np.add.at(confusion, (true_tier, pred_tier), 1)
    return {
        "n": int(true_tier.size),
        "exact_accuracy": _ratio(int((true_tier == pred_tier).sum()), true_tier.size),
        "within_one_accuracy": _ratio(int((np.abs(true_tier - pred_tier) <= 1).sum()), true_tier.size),
        "alert_recall": _ratio(hits, int(true_alert.sum())),
        "alert_precision": _ratio(hits, int(pred_alert.sum())),
        "alert_hits": hits,
        "true_alerts": int(true_alert.sum()),
        "predicted_alerts": int(pred_alert.sum()),
        "decision_scale": decision_scale,
        "confusion_matrix": confusion.tolist(),
    }


def pooled_tier_metrics(groups, decision_scale: float = 1.0) -> dict:
    """tier_metrics summed over (y_true, y_pred, thresholds) groups, e.g. one group per fold."""
    parts = [tier_metrics(y_true, y_pred, thr, decision_scale) for y_true, y_pred, thr in groups]
    confusion = np.sum([p["confusion_matrix"] for p in parts], axis=0)
    true_idx, pred_idx = np.indices(confusion.shape)
    n = int(confusion.sum())
    hits = sum(p["alert_hits"] for p in parts)
    true_alerts = sum(p["true_alerts"] for p in parts)
    predicted_alerts = sum(p["predicted_alerts"] for p in parts)
    return {
        "n": n,
        "exact_accuracy": _ratio(int(np.trace(confusion)), n),
        "within_one_accuracy": _ratio(int(confusion[np.abs(true_idx - pred_idx) <= 1].sum()), n),
        "alert_recall": _ratio(hits, true_alerts),
        "alert_precision": _ratio(hits, predicted_alerts),
        "alert_hits": hits,
        "true_alerts": true_alerts,
        "predicted_alerts": predicted_alerts,
        "decision_scale": decision_scale,
        "confusion_matrix": confusion.tolist(),
    }


def alert_tradeoff(groups) -> list[dict]:
    """Pooled alert recall/precision for each candidate decision scale."""
    rows = []
    for scale in DECISION_SCALES:
        pooled = pooled_tier_metrics(groups, scale)
        rows.append(
            {
                "decision_scale": scale,
                "alert_recall": pooled["alert_recall"],
                "alert_precision": pooled["alert_precision"],
            }
        )
    return rows


def choose_decision_scale(tradeoff: list[dict], min_recall: float = MIN_ALERT_RECALL) -> float:
    """Largest scale (fewest false alarms) whose recall meets the target; else the smallest scale."""
    meeting = [r["decision_scale"] for r in tradeoff if (r["alert_recall"] or 0) >= min_recall]
    return max(meeting) if meeting else min(r["decision_scale"] for r in tradeoff)
