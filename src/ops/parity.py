"""Python -> TypeScript golden fixtures: python -m src.ops.parity

Runs PARITY_SCENARIOS through the Python decision core and writes every output the
dashboard recomputes in the browser (demand, allocation, routing, crews, prevented cases,
SMS, WhatsApp, briefs) to tests/fixtures/ops_parity.json. scripts/test-ops.test.ts runs
the same scenarios through the TypeScript port and must reproduce them; the scenario_id
uses the git commit recorded in public/data/ops/config.json, as the browser does.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict

from src import config as cfg
from src.ops.allocate import region_summary
from src.ops.brief import render_brief
from src.ops.dispatch_text import render_sms, render_whatsapp
from src.ops.notices import build_notices
from src.ops.pipeline import Context, ScenarioRun, load_context, run_scenario
from src.ops.scenario import Scenario
from src.ops.ui_export import OUT_DIR

FIXTURE_PATH = cfg.ROOT / "tests" / "fixtures" / "ops_parity.json"
GENERATED_AT = "2026-11-27 10:15"
BRIEF_WARDS = ("CCC_Ward_01", "DNCC_Ward_05")
PARITY_SCENARIOS = (
    Scenario(),
    Scenario(stock_pct=60),
    Scenario(stock_pct=30, floor_pct=25, confidence="bad", weeks=4, crews_total=40, crew_mode="roi", band="high"),
    Scenario(asof="2025-07-14", weeks=3, crews_total=0, apply_intervention=False),
    Scenario(asof="2025-12-29", weeks=1),
    Scenario(asof="2024-08-05", stock_pct=45, floor_pct=0, crews_total=10, band="low"),
)


def _records(table, cols) -> list[dict]:
    return json.loads(table[list(cols)].to_json(orient="records"))


def scenario_fixture(run: ScenarioRun) -> dict:
    notices = build_notices(run, GENERATED_AT)
    return {
        "scenario": asdict(run.scenario),
        "scenario_id": run.scenario_id,
        "crews": {ward: int(c) for ward, c in run.crews.items()},
        "demand": _records(
            run.demand,
            (cfg.WARD_COL, "cases", "peak_weekly_cases", *cfg.SUPPLY_COLS, "risk_rank"),
        ),
        "allocation": _records(
            run.allocation,
            (cfg.WARD_COL, "resource", "priority", "priority_rank", "need", "floor", "allocated", "fill", "alert"),
        ),
        "summary": region_summary(run.allocation),
        "transfers": _records(run.routing.transfers, ("city", "from_ward", "to_ward", "patients")),
        "routing_wards": _records(
            run.routing.wards,
            (cfg.WARD_COL, "required", "capacity", "usable", "sent", "received", "unplaced", "headroom_after"),
        ),
        "cities": _records(run.routing.cities, ("city", "required", "capacity", "moved", "unplaced", "alert")),
        "prevented": {ward: float(v) for ward, v in run.sim.groupby(cfg.WARD_COL)["prevented"].sum().items()},
        "sms": {n.ward_id: render_sms(n) for n in notices},
        "whatsapp": {n.ward_id: render_whatsapp(n) for n in notices},
        "briefs": {n.ward_id: render_brief(n) for n in notices if n.ward_id in BRIEF_WARDS},
    }


def build_fixtures(ctx: Context) -> dict:
    return {
        "provenance": {"data_hash": ctx.data_hash, "git_commit": ctx.git_commit},
        "generated_at": GENERATED_AT,
        "scenarios": [scenario_fixture(run_scenario(s, ctx)) for s in PARITY_SCENARIOS],
    }


def dashboard_commit() -> str:
    """The git commit the browser uses for scenario_id: the one in config.json."""
    config = json.loads((OUT_DIR / "config.json").read_text(encoding="utf-8"))
    return config["provenance"]["git_commit"]


def main() -> int:
    fixtures = build_fixtures(load_context(git_commit=dashboard_commit()))
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(fixtures, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {FIXTURE_PATH} ({FIXTURE_PATH.stat().st_size / 1e6:.2f} MB, {len(PARITY_SCENARIOS)} scenarios)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
