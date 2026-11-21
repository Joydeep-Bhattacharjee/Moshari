import numpy as np
import pytest

from src.tiers import (
    assign_tiers,
    choose_decision_scale,
    fit_thresholds,
    pooled_tier_metrics,
    tier_metrics,
)

THRESHOLDS = (5.0, 9.0, 14.0)


def test_thresholds_are_quantiles_of_positive_targets():
    y = np.concatenate([np.zeros(100), np.arange(1, 101)])
    assert fit_thresholds(y) == pytest.approx((50.5, 75.25, 90.1))


def test_thresholds_must_increase():
    with pytest.raises(ValueError, match="strictly increasing"):
        fit_thresholds([0, 5, 5, 5, 5])


def test_thresholds_need_positive_targets():
    with pytest.raises(ValueError, match="no positive targets"):
        fit_thresholds([0, 0, 0])


def test_tier_boundaries():
    values = [0, 4.99, 5, 8.99, 9, 13.99, 14, 40]
    assert assign_tiers(values, THRESHOLDS).tolist() == [0, 0, 1, 1, 2, 2, 3, 3]


def test_tier_metrics_on_hand_example():
    # true tiers [Low, High, Critical, Critical]; predicted [Low, High, Low, Critical]
    m = tier_metrics([0, 10, 20, 15], [0, 10, 3, 20], THRESHOLDS)
    assert m["exact_accuracy"] == 0.75
    assert m["within_one_accuracy"] == 0.75
    assert m["alert_recall"] == pytest.approx(0.6667)
    assert m["alert_precision"] == 1.0
    assert m["confusion_matrix"][3] == [1, 0, 0, 1]


def test_lower_decision_scale_raises_recall():
    low = tier_metrics([0, 10, 20, 15], [0, 10, 3, 20], THRESHOLDS, decision_scale=0.2)
    assert low["alert_recall"] == 1.0
    assert low["decision_scale"] == 0.2


def test_no_predicted_alerts_gives_no_precision():
    assert tier_metrics([20], [0], THRESHOLDS)["alert_precision"] is None


def test_pooled_metrics_sum_groups_with_their_own_thresholds():
    groups = [([10], [10], THRESHOLDS), ([10], [10], (20.0, 30.0, 40.0))]
    pooled = pooled_tier_metrics(groups)
    assert pooled["n"] == 2
    assert pooled["true_alerts"] == 1  # 10 cases is High only under the first thresholds
    assert pooled["alert_recall"] == 1.0
    assert pooled["exact_accuracy"] == 1.0


def test_choose_decision_scale_prefers_fewest_false_alarms():
    tradeoff = [
        {"decision_scale": 1.0, "alert_recall": 0.6},
        {"decision_scale": 0.9, "alert_recall": 0.72},
        {"decision_scale": 0.8, "alert_recall": 0.8},
    ]
    assert choose_decision_scale(tradeoff) == 0.9
    assert choose_decision_scale(tradeoff, min_recall=0.95) == 0.8
