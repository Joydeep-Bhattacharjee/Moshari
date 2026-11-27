"""What-if vector-control simulator (PRD 6.3): crews lower water-logging, the model re-runs.

  reduction_w = r_max * (1 - exp(-crews_w / c_sat))            r_max by band, c_sat = 2
  wl'_w,t     = max(0.22, wl_w * (1 - reduction_w * ramp_t))   ramp 0, .5, 1, 1 for weeks +1..+4
  ratio_w,t   = GLM(rows_w | wl') / GLM(rows_w | wl)           2- or 3-week Poisson GLM, re-run
  after_w,t   = baseline_w,t * ratio_w,t                       expected, P10 and P90
  prevented   = baseline - after

Why the ratio comes from the GLMs: their water-logging terms both have positive
coefficients, so log(cases) moves by (b_wl + b_int * recent_rain) * d_wl. Lowering
water-logging can then only lower cases, and each extra crew prevents less than the last
(concave), which also makes the marginal-gain auto-suggest optimal. The 4-week tree model
is constrained in water-logging but not in rain x water-logging, which an intervention
also lowers, and the P90 models are unconstrained, so their forecast can rise when
water-logging falls (by up to 0.5 case). They keep their baselines and take the GLM ratio;
week +4 uses the 3-week GLM on the same as-of rows. This is model-based sensitivity, not a causal estimate: the index is static
per ward, so its effect was learned across wards. r_max is an assumption to calibrate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config as cfg
from src.ops.forecast_window import WINDOW_COLS
from src.predict import rows_for
from src.tiers import TIERS, assign_tiers

BANDS = {"low": 0.15, "base": 0.30, "high": 0.45}  # r_max: maximum water-logging reduction
DEFAULT_BAND = "base"
CREW_SATURATION = 2.0  # c_sat: crews at which ~63% of r_max is reached
MAX_CREWS_PER_WARD = 6
RAMP_BY_WEEK = {1: 0.0, 2: 0.5, 3: 1.0, 4: 1.0}  # spraying shows after 2-4 weeks (rain-lag peak at 3)
WATERLOG_FLOOR = 0.22  # lowest index in the data: no extrapolation below it
EFFECT_HORIZON_BY_WEEK = {1: 2, 2: 2, 3: 3, 4: 3}  # GLM horizon that supplies each week's ratio
INTERACTION_COL = "rain2_4_x_waterlog"
RAIN_SUM_COL = "rain_sum_lag2_4"
SIM_COLS = (
    *WINDOW_COLS,
    "crews",
    "reduction",
    "waterlog",
    "waterlog_after",
    "effect_ratio",
    "expected_after",
    "p90_after",
    "prevented",
    "prevented_p90",
)


def crew_reduction(crews, band: str = DEFAULT_BAND) -> np.ndarray:
    """Share by which crews cut water-logging: r_max * (1 - exp(-crews / c_sat))."""
    if band not in BANDS:
        raise ValueError(f"band must be one of {sorted(BANDS)}, got {band!r}")
    counts = np.asarray(crews, dtype=float)
    if ((counts < 0) | (counts > MAX_CREWS_PER_WARD) | (counts % 1 != 0)).any():
        raise ValueError(f"crews per ward must be whole numbers from 0 to {MAX_CREWS_PER_WARD}")
    return BANDS[band] * (1 - np.exp(-counts / CREW_SATURATION))


def intervened_waterlog(waterlog, reduction, ramp: float) -> np.ndarray:
    """Lowered index, clamped to the observed minimum and never above the original."""
    wl = np.asarray(waterlog, dtype=float)
    lowered = np.maximum(WATERLOG_FLOOR, wl * (1 - np.asarray(reduction, dtype=float) * ramp))
    return np.minimum(wl, lowered)


def drainage_coefficients(bundle: dict) -> dict:
    """Per-unit log-effect of water-logging and of rain x water-logging in each effect GLM."""
    out = {}
    for horizon in sorted(set(EFFECT_HORIZON_BY_WEEK.values())):
        model = bundle["models"][horizon]["point"]
        steps = getattr(model.estimator, "named_steps", {})
        if "poissonregressor" not in steps:
            raise ValueError(f"the {horizon}-week effect model must be the Poisson GLM")
        per_unit = steps["poissonregressor"].coef_ / steps["standardscaler"].scale_
        cols = list(model.feature_cols)
        out[horizon] = {
            "waterlog": float(per_unit[cols.index(cfg.WATERLOG_COL)]),
            "rain_x_waterlog": float(per_unit[cols.index(INTERACTION_COL)]),
        }
    return out


def _crew_plan(window: pd.DataFrame, crews: pd.Series) -> pd.Series:
    wards = pd.Index(sorted(window[cfg.WARD_COL].unique()), name=cfg.WARD_COL)
    unknown = sorted(set(crews.index) - set(wards))
    if unknown:
        raise ValueError(f"crews given for wards not in the window: {unknown[:5]}")
    return crews.reindex(wards, fill_value=0).astype(int)


def _with_waterlog(rows: pd.DataFrame, waterlog: np.ndarray) -> pd.DataFrame:
    return rows.assign(**{cfg.WATERLOG_COL: waterlog, INTERACTION_COL: rows[RAIN_SUM_COL] * waterlog})


def _simulate_week(frame, bundle, rows: pd.DataFrame, plan: pd.Series, band: str) -> pd.DataFrame:
    week = int(rows["week_ahead"].iloc[0])
    horizon = EFFECT_HORIZON_BY_WEEK[week]
    wards = rows[cfg.WARD_COL].to_numpy()
    features = rows_for(frame, bundle, rows["origin_week"].iloc[0], horizon).set_index(cfg.WARD_COL).loc[wards]
    crews = plan.loc[wards].to_numpy()
    reduction = crew_reduction(crews, band)
    wl = features[cfg.WATERLOG_COL].to_numpy(dtype=float)
    wl_after = intervened_waterlog(wl, reduction, RAMP_BY_WEEK[week])
    model = bundle["models"][horizon]["point"]
    before = model.predict(features)
    after = model.predict(_with_waterlog(features, wl_after))
    ratio = np.divide(after, before, out=np.ones_like(before), where=before > 0)
    expected, p90 = rows["expected_cases"].to_numpy(), rows["p90_cases"].to_numpy()
    return rows.assign(
        crews=crews,
        reduction=reduction,
        waterlog=wl,
        waterlog_after=wl_after,
        effect_ratio=ratio,
        expected_after=expected * ratio,
        p90_after=p90 * ratio,
        prevented=expected - expected * ratio,
        prevented_p90=p90 - p90 * ratio,
    )


def simulate(
    frame: pd.DataFrame, bundle: dict, window: pd.DataFrame, crews: pd.Series, band: str = DEFAULT_BAND
) -> pd.DataFrame:
    """Baseline vs intervention per ward-week. `crews` maps ward_id -> crews (missing = 0)."""
    plan = _crew_plan(window, crews)
    parts = [
        _simulate_week(frame, bundle, rows, plan, band)
        for _, rows in window.groupby("week_ahead", sort=True)
    ]
    return pd.concat(parts).sort_values([cfg.WARD_COL, "week_ahead"], ignore_index=True)[list(SIM_COLS)]


def intervened_window(sim: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    """The forecast window after the intervention, with tiers re-assigned: feeds demand,
    allocation and routing ("re-plan with intervention")."""
    tier_rank = np.zeros(len(sim), dtype=int)
    for horizon, idx in sim.groupby("model_horizon").indices.items():
        cutoffs = np.asarray(bundle["thresholds"][horizon]) * bundle["decision_scale"][horizon]
        tier_rank[idx] = assign_tiers(sim["expected_after"].to_numpy()[idx], cutoffs)
    return sim.assign(
        expected_cases=sim["expected_after"],
        p10_cases=sim["p10_cases"] * sim["effect_ratio"],
        p90_cases=sim["p90_after"],
        tier_rank=tier_rank,
        tier=[TIERS[i] for i in tier_rank],
    )[list(WINDOW_COLS)]


def prevented_table(frame: pd.DataFrame, bundle: dict, window: pd.DataFrame, band: str = DEFAULT_BAND) -> pd.DataFrame:
    """Cases prevented over the window per ward (rows) for 0..MAX crews in that ward (columns)."""
    wards = sorted(window[cfg.WARD_COL].unique())
    columns = {
        crews: simulate(frame, bundle, window, pd.Series(crews, index=wards), band)
        .groupby(cfg.WARD_COL)["prevented"]
        .sum()
        for crews in range(MAX_CREWS_PER_WARD + 1)
    }
    return pd.DataFrame(columns).rename_axis(cfg.WARD_COL)


def auto_suggest(table: pd.DataFrame, total_crews: int) -> pd.Series:
    """Give crews one at a time to the largest marginal gain (optimal: returns are concave)."""
    if total_crews < 0:
        raise ValueError(f"total crews must be >= 0, got {total_crews}")
    values = table.to_numpy(dtype=float)
    gains = np.diff(values, axis=1)  # gains[w, c] = cases prevented by crew c + 1 in ward w
    top = gains.shape[1]
    assigned = np.zeros(len(values), dtype=int)
    for _ in range(int(total_crews)):
        nxt = np.where(assigned < top, gains[np.arange(len(values)), np.minimum(assigned, top - 1)], -np.inf)
        best = int(np.argmax(nxt))  # first maximum = lowest ward_id
        if nxt[best] <= 0:
            break  # no ward benefits from another crew
        assigned[best] += 1
    return pd.Series(assigned, index=table.index, name="crews")


def roi_leaderboard(table: pd.DataFrame) -> pd.DataFrame:
    """Cases prevented over the window by one crew in each ward, best first (ties by ward_id)."""
    board = pd.DataFrame({cfg.WARD_COL: table.index, "prevented_per_crew": table[1].to_numpy()})
    ranked = board.sort_values(["prevented_per_crew", cfg.WARD_COL], ascending=[False, True], ignore_index=True)
    return ranked.assign(rank=np.arange(1, len(ranked) + 1))
