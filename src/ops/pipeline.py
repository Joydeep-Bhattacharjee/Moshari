"""End-to-end decision chain for one Scenario (PRD 4):

forecast window -> crew plan (priority order or ROI auto-suggest) -> simulate ->
post-intervention window -> demand -> allocation -> overflow routing.

Crews are planned on the baseline forecast; supplies and beds are then planned on the
forecast after spraying ("re-plan with intervention"), unless the scenario turns it off.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src import config as cfg
from src.data import load_weekly
from src.features import build_features
from src.ops.allocate import allocate, priority_scores
from src.ops.capacity import bed_capacity
from src.ops.crews import assign_crews, crews_needed
from src.ops.demand import ward_demand
from src.ops.forecast_window import forecast_window
from src.ops.overflow import RoutingResult, route_overflow
from src.ops.scenario import Scenario, scenario_id
from src.ops.simulate import auto_suggest, intervened_window, prevented_table, simulate
from src.ops.wards import ward_attributes
from src.predict import load_bundle

DATA_HASH_CHARS = 16


@dataclass(frozen=True)
class Context:
    """Everything that does not change between scenarios: model, features, ward tables."""

    bundle: dict
    frame: pd.DataFrame
    wards: pd.DataFrame
    capacity: pd.DataFrame
    data_hash: str
    git_commit: str


@dataclass(frozen=True)
class ScenarioRun:
    scenario: Scenario
    scenario_id: str
    window: pd.DataFrame
    crews: pd.Series
    sim: pd.DataFrame
    plan_window: pd.DataFrame
    demand: pd.DataFrame
    allocation: pd.DataFrame
    routing: RoutingResult


def file_hash(path: Path) -> str:
    """sha256 of the file with CRLF read as LF: git autocrlf gives Windows checkouts CRLF and
    Linux checkouts LF, and the same data must give the same hash (and scenario_id) on both."""
    content = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()[:DATA_HASH_CHARS]


def load_context(data_path: Path = cfg.ONSITE_DATA_PATH, git_commit: str = "unknown") -> Context:
    bundle = load_bundle()
    weekly = load_weekly(data_path)
    return Context(
        bundle=bundle,
        frame=build_features(weekly, bundle["feature_params"]),
        wards=ward_attributes(weekly),
        capacity=bed_capacity(pd.read_csv(data_path), bundle["train_end"]),
        data_hash=file_hash(data_path),
        git_commit=git_commit,
    )


def _with_ward_attributes(demand: pd.DataFrame, wards: pd.DataFrame) -> pd.DataFrame:
    return demand.merge(wards[[cfg.WARD_COL, cfg.DENSITY_COL, cfg.WATERLOG_COL]], on=cfg.WARD_COL)


def _crew_plan(scenario: Scenario, ctx: Context, window: pd.DataFrame, density_ref: float) -> pd.Series:
    if scenario.crew_mode == "roi":
        table = prevented_table(ctx.frame, ctx.bundle, window, scenario.band)
        return auto_suggest(table, scenario.crews_total).rename_axis(cfg.WARD_COL)
    baseline = _with_ward_attributes(ward_demand(window, scenario.confidence), ctx.wards)
    ranked = priority_scores(baseline, density_ref).sort_values("priority_rank")
    need = crews_needed(ranked["risk_rank"].to_numpy(), ranked[cfg.WATERLOG_COL].to_numpy())
    plan = pd.Series(assign_crews(need, scenario.crews_total), index=ranked[cfg.WARD_COL].to_numpy(), name="crews")
    return plan.sort_index().rename_axis(cfg.WARD_COL)


def _routing_table(allocation: pd.DataFrame, demand: pd.DataFrame, capacity: pd.DataFrame) -> pd.DataFrame:
    priority = allocation.drop_duplicates(cfg.WARD_COL)[[cfg.WARD_COL, "priority"]]
    beds = demand[[cfg.WARD_COL, cfg.CITY_COL, cfg.BEDS_COL]]
    return beds.merge(priority, on=cfg.WARD_COL).merge(capacity[[cfg.WARD_COL, "capacity"]], on=cfg.WARD_COL)


def run_scenario(scenario: Scenario, ctx: Context) -> ScenarioRun:
    density_ref = float(ctx.wards[cfg.DENSITY_COL].max())
    window = forecast_window(ctx.frame, ctx.bundle, scenario.asof, scenario.weeks)
    crews = _crew_plan(scenario, ctx, window, density_ref)
    sim = simulate(ctx.frame, ctx.bundle, window, crews, scenario.band)
    plan_window = intervened_window(sim, ctx.bundle) if scenario.apply_intervention else window
    demand = _with_ward_attributes(ward_demand(plan_window, scenario.confidence), ctx.wards)
    allocation = allocate(demand, scenario.stock_pct, scenario.floor_pct, density_ref)
    routing = route_overflow(_routing_table(allocation, demand, ctx.capacity))
    return ScenarioRun(
        scenario=scenario,
        scenario_id=scenario_id(scenario, ctx.data_hash, ctx.git_commit),
        window=window,
        crews=crews,
        sim=sim,
        plan_window=plan_window,
        demand=demand,
        allocation=allocation,
        routing=routing,
    )
