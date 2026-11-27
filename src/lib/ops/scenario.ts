// Scenario validation and scenario_id (mirror of src/ops/scenario.py).
import { sha1Hex } from "./sha1.ts";
import type { OpsConstants, Scenario } from "./types.ts";

const FIELDS: (keyof Scenario)[] = [
  "apply_intervention",
  "asof",
  "band",
  "confidence",
  "crew_mode",
  "crews_total",
  "floor_pct",
  "stock_pct",
  "weeks",
]; // sorted, like json.dumps(sort_keys=True)

/** Same bytes as Python's json.dumps(asdict(s), sort_keys=True, separators=(",", ":")). */
export function canonicalJson(s: Scenario): string {
  return "{" + FIELDS.map((f) => `${JSON.stringify(f)}:${JSON.stringify(s[f])}`).join(",") + "}";
}

export function scenarioId(s: Scenario, dataHash: string, gitCommit: string): string {
  return sha1Hex(canonicalJson(s) + dataHash + gitCommit).slice(0, 8);
}

/** Problems with a scenario, empty when it is valid (Python raises on the same rules). */
export function scenarioErrors(s: Scenario, c: OpsConstants, asofWeeks: string[]): string[] {
  const checks: [boolean, string][] = [
    [
      asofWeeks.includes(s.asof),
      `as-of week must be a Monday from ${asofWeeks[0]} to ${asofWeeks[asofWeeks.length - 1]}`,
    ],
    [Number.isInteger(s.weeks) && s.weeks >= 1 && s.weeks <= c.max_window_weeks, "weeks must be 1 to 4"],
    [
      Number.isInteger(s.stock_pct) && s.stock_pct >= c.stock_pct_range[0] && s.stock_pct <= c.stock_pct_range[1],
      "stock_pct must be 30 to 100",
    ],
    [Number.isInteger(s.floor_pct) && s.floor_pct >= 0 && s.floor_pct <= 100, "floor_pct must be 0 to 100"],
    [s.confidence === "likely" || s.confidence === "bad", "confidence must be likely or bad"],
    [Number.isInteger(s.crews_total) && s.crews_total >= 0, "crews_total must be >= 0"],
    [s.crew_mode === "priority" || s.crew_mode === "roi", "crew_mode must be priority or roi"],
    [s.band in c.bands, "band must be low, base or high"],
  ];
  return checks.filter(([ok]) => !ok).map(([, message]) => message);
}
