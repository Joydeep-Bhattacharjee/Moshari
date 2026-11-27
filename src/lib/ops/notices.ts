// Per-ward dispatch notice fields (mirror of src/ops/notices.py), read only from a
// ScenarioRun's tables so the notices cannot disagree with them.
import { compareText } from "./numeric.ts";
import type { ScenarioRun } from "./pipeline.ts";
import type { OpsConfig } from "./types.ts";
import { KITS, SALINE } from "./types.ts";

const HIGH_RISK_FROM = 2; // tier index of "High": daily reporting from here up
export const ROUTINE = "Routine surveillance: no extra action needed this window.";

export interface WeekBand {
  targetWeek: string;
  expected: number;
  p10: number;
  p90: number;
  actual: number | null;
}

export interface Notice {
  wardId: string;
  city: string;
  risk: string;
  riskRank: number;
  casesP50: number;
  casesP90: number;
  weeks: WeekBand[];
  salineAllocated: number;
  salineRequired: number;
  kitsAllocated: number;
  kitsRequired: number;
  bedsRequired: number;
  bedsCapacity: number;
  capacitySource: string;
  crews: number;
  sends: [string, number][];
  receives: [string, number][];
  unplaced: number;
  asof: string;
  scenarioId: string;
  generatedAt: string;
  salineShort: number;
  kitsShort: number;
  deficit: boolean;
}

/** Round a forecast for display, half up (floor(x + 0.5)), identical to Python. */
export function displayCases(value: number): number {
  return Math.floor(value + 0.5) + 0;
}

export function plural(count: number, word: string): string {
  return count === 1 ? `${count} ${word}` : `${count} ${word}s`;
}

export function actions(n: Notice): string[] {
  const steps: string[] = [];
  if (n.salineShort) steps.push(`Request ${plural(n.salineShort, "more saline bag")} (emergency procurement).`);
  if (n.kitsShort) steps.push(`Request ${plural(n.kitsShort, "more test kit")}.`);
  for (const [ward, k] of n.sends) steps.push(`Transfer ${plural(k, "patient")} to ${ward} (same city).`);
  for (const [ward, k] of n.receives) steps.push(`Prepare ${plural(k, "bed")} for patients from ${ward}.`);
  if (n.unplaced) {
    steps.push(
      `Escalate: ${plural(n.unplaced, "patient")} without a bed in ${n.city}; request field beds or regional support.`,
    );
  }
  if (n.crews) steps.push(`Deploy ${plural(n.crews, "spray crew")} to clear standing water.`);
  if (n.riskRank >= HIGH_RISK_FROM) steps.push("Report cases daily to the city health office.");
  return steps.length ? steps : [ROUTINE];
}

export function buildNotices(run: ScenarioRun, generatedAt: string, config: OpsConfig): Notice[] {
  const tiers = config.constants.tiers;
  const demand = new Map(run.demand.map((d) => [d.ward, d]));
  const routing = new Map(run.routing.wards.map((r) => [r.ward, r]));
  const alloc = new Map(run.allocation.map((a) => [`${a.ward}|${a.resource}`, a]));
  const wards = [...new Set(run.planWindow.map((r) => r.ward))].sort(compareText);
  return wards.map((ward) => {
    const rows = run.planWindow.filter((r) => r.ward === ward).sort((a, b) => a.weekAhead - b.weekAhead);
    const d = demand.get(ward)!;
    const r = routing.get(ward)!;
    const saline = alloc.get(`${ward}|${SALINE}`)!;
    const kits = alloc.get(`${ward}|${KITS}`)!;
    const salineShort = saline.need - saline.allocated;
    const kitsShort = kits.need - kits.allocated;
    return {
      wardId: ward,
      city: d.city,
      risk: tiers[d.riskRank],
      riskRank: d.riskRank,
      casesP50: displayCases(Math.max(...rows.map((w) => w.expected))),
      casesP90: displayCases(Math.max(...rows.map((w) => w.p90))),
      weeks: rows.map((w) => ({ targetWeek: w.targetWeek, expected: w.expected, p10: w.p10, p90: w.p90, actual: w.actual })),
      salineAllocated: saline.allocated,
      salineRequired: saline.need,
      kitsAllocated: kits.allocated,
      kitsRequired: kits.need,
      bedsRequired: r.required,
      bedsCapacity: r.capacity,
      capacitySource: config.provenance.capacity_source,
      crews: run.crews.get(ward) ?? 0,
      sends: run.routing.transfers.filter((t) => t.fromWard === ward).map((t) => [t.toWard, t.patients]),
      receives: run.routing.transfers.filter((t) => t.toWard === ward).map((t) => [t.fromWard, t.patients]),
      unplaced: r.unplaced,
      asof: run.scenario.asof,
      scenarioId: run.scenarioId,
      generatedAt,
      salineShort,
      kitsShort,
      deficit: salineShort > 0 || kitsShort > 0 || r.unplaced > 0,
    };
  });
}
