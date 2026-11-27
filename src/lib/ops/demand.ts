// Supply demand per ward (mirror of src/ops/demand.py). The dataset rounds .5 down:
// units = ceil(max(cases, 0) * per_1000 / 1000 - 0.5).
import { kahanSum, noNegativeZero, compareText } from "./numeric.ts";
import type { Confidence, DemandRow, OpsConfig, WindowRow } from "./types.ts";
import { BEDS, KITS, SALINE } from "./types.ts";

export function supplyUnits(cases: number, per1000: number): number {
  if (per1000 < 0) throw new Error(`per_1000 must be >= 0, got ${per1000}`);
  if (Number.isNaN(cases)) throw new Error("case counts contain NaN");
  const scaled = (Math.max(cases, 0) * per1000) / 1000;
  return noNegativeZero(Math.ceil(scaled - 0.5));
}

/** One row per ward, sorted by ward id. Saline and kits add up; beds take the peak week. */
export function wardDemand(window: WindowRow[], confidence: Confidence, config: OpsConfig): DemandRow[] {
  if (window.length === 0) throw new Error("forecast window is empty");
  const per1000 = config.constants.supply_per_1000;
  const attributes = new Map(config.wards.map((w) => [w.id, w]));
  const byWard = new Map<string, WindowRow[]>();
  for (const row of window) byWard.set(row.ward, [...(byWard.get(row.ward) ?? []), row]);
  return [...byWard.keys()].sort(compareText).map((ward) => {
    const rows = byWard.get(ward)!;
    const cases = rows.map((r) => Math.max(confidence === "bad" ? r.p90 : r.expected, 0));
    const attr = attributes.get(ward)!;
    return {
      ward,
      city: rows[0].city,
      windowWeeks: new Set(rows.map((r) => r.weekAhead)).size,
      cases: kahanSum(cases),
      peakWeeklyCases: Math.max(...cases),
      saline: cases.reduce((sum, c) => sum + supplyUnits(c, per1000[SALINE]), 0),
      kits: cases.reduce((sum, c) => sum + supplyUnits(c, per1000[KITS]), 0),
      beds: Math.max(...cases.map((c) => supplyUnits(c, per1000[BEDS]))),
      riskRank: Math.max(...rows.map((r) => r.tierRank)),
      density: attr.density,
      waterlog: attr.waterlog,
    };
  });
}
