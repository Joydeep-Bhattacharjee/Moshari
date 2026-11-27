// Props every Operations screen receives, plus the per-ward joins they share.
import type { ScenarioRun } from "../lib/ops/pipeline.ts";
import type { Alert, OpsConfig, OpsForecasts, Scenario, WindowRow } from "../lib/ops/types.ts";
import { KITS, SALINE } from "../lib/ops/types.ts";
import { sum, worstAlert } from "./format";

export type ScreenProps = {
  run: ScenarioRun;
  config: OpsConfig;
  forecasts: OpsForecasts;
  scenario: Scenario;
  onChange: (patch: Partial<Scenario>) => void;
  onExplain: (ward: string) => void;
};

export interface WardRow {
  ward: string;
  city: string;
  priorityRank: number;
  priority: number;
  riskRank: number;
  cases: number;
  salineNeed: number;
  salineAlloc: number;
  kitsNeed: number;
  kitsAlloc: number;
  beds: number;
  capacity: number;
  sent: number;
  received: number;
  unplaced: number;
  crews: number;
  alert: Alert;
}

/** One row per ward joining demand, allocation, routing and crews, in priority order. */
export function wardRows(run: ScenarioRun): WardRow[] {
  const demand = new Map(run.demand.map((d) => [d.ward, d]));
  const routing = new Map(run.routing.wards.map((r) => [r.ward, r]));
  const kits = new Map(run.allocation.filter((a) => a.resource === KITS).map((a) => [a.ward, a]));
  return run.allocation
    .filter((a) => a.resource === SALINE)
    .map((s) => {
      const k = kits.get(s.ward)!;
      const d = demand.get(s.ward)!;
      const r = routing.get(s.ward)!;
      return {
        ward: s.ward,
        city: s.city,
        priorityRank: s.priorityRank,
        priority: s.priority,
        riskRank: s.riskRank,
        cases: d.cases,
        salineNeed: s.need,
        salineAlloc: s.allocated,
        kitsNeed: k.need,
        kitsAlloc: k.allocated,
        beds: d.beds,
        capacity: r.capacity,
        sent: r.sent,
        received: r.received,
        unplaced: r.unplaced,
        crews: run.crews.get(s.ward) ?? 0,
        alert: worstAlert([s.alert, k.alert]),
      };
    });
}

export interface WeekTotal {
  week: string;
  expected: number;
  p10: number;
  p90: number;
  actual: number | null;
}

/** Region totals per target week. Summed P10/P90 are a band, not a quantile of the sum. */
export function weeklyTotals(rows: WindowRow[]): WeekTotal[] {
  const weeks = [...new Set(rows.map((r) => r.targetWeek))].sort();
  return weeks.map((week) => {
    const part = rows.filter((r) => r.targetWeek === week);
    const actuals = part.map((r) => r.actual);
    return {
      week,
      expected: sum(part.map((r) => r.expected)),
      p10: sum(part.map((r) => r.p10)),
      p90: sum(part.map((r) => r.p90)),
      actual: actuals.every((a) => a !== null) ? sum(actuals as number[]) : null,
    };
  });
}
