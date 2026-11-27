"""Scenario: every user setting for one run, and its traceable scenario_id (PRD 4).

scenario_id = sha1(canonical settings JSON + data_hash + git_commit)[:8], printed on
every screen and export, so any number can be traced to the exact settings, data file
and code version that produced it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from src.ops.allocate import DEFAULT_FLOOR_PCT, DEFAULT_STOCK_PCT, STOCK_PCT_RANGE
from src.ops.demand import CONFIDENCE_COLS, DEFAULT_CONFIDENCE
from src.ops.forecast_window import DEFAULT_WINDOW_WEEKS, WINDOW_PLAN
from src.ops.simulate import BANDS, DEFAULT_BAND

DEFAULT_ASOF = "2025-06-30"  # 2025 city-wide peak week; the data ends off-season
DEFAULT_CREWS_TOTAL = 20  # assumption: the PRD leaves the crew pool to the user
CREW_MODES = ("priority", "roi")  # priority order up to need, or auto-suggest by ROI


@dataclass(frozen=True)
class Scenario:
    asof: str = DEFAULT_ASOF
    weeks: int = DEFAULT_WINDOW_WEEKS
    stock_pct: int = DEFAULT_STOCK_PCT
    floor_pct: int = DEFAULT_FLOOR_PCT
    confidence: str = DEFAULT_CONFIDENCE
    crews_total: int = DEFAULT_CREWS_TOTAL
    crew_mode: str = "priority"
    band: str = DEFAULT_BAND
    apply_intervention: bool = True  # re-plan supplies and beds on the post-crew forecast

    def __post_init__(self) -> None:
        checks = [
            (self.weeks in WINDOW_PLAN, f"weeks must be 1 to {max(WINDOW_PLAN)}"),
            (STOCK_PCT_RANGE[0] <= self.stock_pct <= STOCK_PCT_RANGE[1], "stock_pct must be 30 to 100"),
            (0 <= self.floor_pct <= 100, "floor_pct must be 0 to 100"),
            (self.confidence in CONFIDENCE_COLS, f"confidence must be one of {sorted(CONFIDENCE_COLS)}"),
            (self.crews_total >= 0, "crews_total must be >= 0"),
            (self.crew_mode in CREW_MODES, f"crew_mode must be one of {CREW_MODES}"),
            (self.band in BANDS, f"band must be one of {sorted(BANDS)}"),
        ]
        errors = [message for ok, message in checks if not ok]
        if errors:
            raise ValueError("invalid scenario: " + "; ".join(errors))


def canonical_json(scenario: Scenario) -> str:
    return json.dumps(asdict(scenario), sort_keys=True, separators=(",", ":"))


def scenario_id(scenario: Scenario, data_hash: str, git_commit: str) -> str:
    payload = canonical_json(scenario) + data_hash + git_commit
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
