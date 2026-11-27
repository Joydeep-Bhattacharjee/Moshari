"""Spray-crew need per ward and the default priority-order assignment (PRD 6.1).

crews_need_w = tier crews (Low 0, Medium 1, High 2, Critical 3)
               + 1 if water_logging_risk_index >= 0.75.
The ROI-optimised assignment lives with the simulator; this is the starting plan.
"""
from __future__ import annotations

import numpy as np

from src.ops.allocate import greedy_fill

CREWS_BY_TIER = (0, 1, 2, 3)
POOR_DRAINAGE_FROM = 0.75  # water-logging index that earns one extra crew


def crews_needed(risk_rank: np.ndarray, waterlog: np.ndarray) -> np.ndarray:
    tier_crews = np.asarray(CREWS_BY_TIER)[np.asarray(risk_rank, dtype=int)]
    return tier_crews + (np.asarray(waterlog, dtype=float) >= POOR_DRAINAGE_FROM).astype(int)


def assign_crews(need_in_priority_order: np.ndarray, total_crews: int) -> np.ndarray:
    """Give each ward, in priority order, up to its need until the crews run out."""
    if total_crews < 0:
        raise ValueError(f"total crews must be >= 0, got {total_crews}")
    return greedy_fill(need_in_priority_order, int(total_crews))
