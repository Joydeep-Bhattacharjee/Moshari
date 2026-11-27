// What-if vector-control simulator (mirror of src/ops/simulate.py).
// Python re-runs the Poisson GLM; the browser uses its closed form,
// ratio = exp(-(b_wl + b_int * recent_rain) * (wl - wl')), which tests/test_ui_export.py
// shows equals re-running the model to 1e-12.
import { argmax, compareText, kahanSum, searchsortedRight } from "./numeric.ts";
import type { Band, DrainageCoef, OpsConfig, OpsConstants, SimRow, WindowRow } from "./types.ts";

export function crewReduction(crews: number, band: Band, c: OpsConstants): number {
  if (!(band in c.bands)) throw new Error(`band must be one of low, base, high, got ${band}`);
  if (!Number.isInteger(crews) || crews < 0 || crews > c.max_crews_per_ward) {
    throw new Error(`crews per ward must be whole numbers from 0 to ${c.max_crews_per_ward}`);
  }
  return c.bands[band] * (1 - Math.exp(-crews / c.crew_saturation));
}

/** Lowered index, clamped to the observed minimum and never above the original. */
export function intervenedWaterlog(waterlog: number, reduction: number, ramp: number, c: OpsConstants): number {
  const lowered = Math.max(c.waterlog_floor, waterlog * (1 - reduction * ramp));
  return Math.min(waterlog, lowered);
}

export function effectRatio(coef: DrainageCoef, rainSum: number, waterlog: number, waterlogAfter: number): number {
  return Math.exp(-(coef.waterlog + coef.rain_x_waterlog * rainSum) * (waterlog - waterlogAfter));
}

export function simulate(
  window: WindowRow[],
  crews: Map<string, number>,
  band: Band,
  config: OpsConfig,
  rain: Map<string, number>,
): SimRow[] {
  const c = config.constants;
  const waterlog = new Map(config.wards.map((w) => [w.id, w.waterlog]));
  return window.map((row) => {
    const count = crews.get(row.ward) ?? 0;
    const reduction = crewReduction(count, band, c);
    const wl = waterlog.get(row.ward)!;
    const wlAfter = intervenedWaterlog(wl, reduction, c.ramp_by_week[String(row.weekAhead)], c);
    const coef = config.drainage[String(c.effect_horizon_by_week[String(row.weekAhead)])];
    const ratio = effectRatio(coef, rain.get(row.ward)!, wl, wlAfter);
    return {
      ...row,
      crews: count,
      reduction,
      waterlog: wl,
      waterlogAfter: wlAfter,
      effectRatio: ratio,
      expectedAfter: row.expected * ratio,
      p90After: row.p90 * ratio,
      prevented: row.expected - row.expected * ratio,
    };
  });
}

/** The forecast window after the intervention, with tiers re-assigned. */
export function intervenedWindow(sim: SimRow[], c: OpsConstants): WindowRow[] {
  return sim.map((s) => {
    const h = String(s.modelHorizon);
    const cutoffs = c.thresholds[h].map((t) => t * c.decision_scale[h]);
    return {
      ward: s.ward,
      city: s.city,
      weekAhead: s.weekAhead,
      targetWeek: s.targetWeek,
      modelHorizon: s.modelHorizon,
      expected: s.expectedAfter,
      p10: s.p10 * s.effectRatio,
      p90: s.p90After,
      tierRank: searchsortedRight(cutoffs, s.expectedAfter),
      actual: s.actual,
      topDriver: s.topDriver,
    };
  });
}

/** Cases prevented over the window per ward for 0..max crews in that ward. */
export function preventedTable(
  window: WindowRow[],
  band: Band,
  config: OpsConfig,
  rain: Map<string, number>,
): Map<string, number[]> {
  const wards = [...new Set(window.map((r) => r.ward))].sort(compareText);
  const table = new Map(wards.map((w) => [w, [] as number[]]));
  for (let count = 0; count <= config.constants.max_crews_per_ward; count++) {
    const sim = simulate(window, new Map(wards.map((w) => [w, count])), band, config, rain);
    for (const ward of wards) {
      const rows = sim.filter((s) => s.ward === ward).sort((a, b) => a.weekAhead - b.weekAhead);
      table.get(ward)!.push(kahanSum(rows.map((s) => s.prevented)));
    }
  }
  return table;
}

/** Give crews one at a time to the largest marginal gain (optimal: returns are concave). */
export function autoSuggest(table: Map<string, number[]>, totalCrews: number): Map<string, number> {
  if (totalCrews < 0) throw new Error(`total crews must be >= 0, got ${totalCrews}`);
  const wards = [...table.keys()].sort(compareText);
  const gains = wards.map((w) => table.get(w)!.slice(1).map((v, i) => v - table.get(w)![i]));
  const top = gains[0]?.length ?? 0;
  const assigned = wards.map(() => 0);
  for (let crew = 0; crew < totalCrews; crew++) {
    const next = assigned.map((a, i) => (a < top ? gains[i][Math.min(a, top - 1)] : -Infinity));
    const best = argmax(next);
    if (next[best] <= 0) break;
    assigned[best] += 1;
  }
  return new Map(wards.map((w, i) => [w, assigned[i]]));
}

export interface RoiEntry {
  ward: string;
  preventedPerCrew: number;
  rank: number;
}

export function roiLeaderboard(table: Map<string, number[]>): RoiEntry[] {
  return [...table.entries()]
    .map(([ward, values]) => ({ ward, preventedPerCrew: values[1], rank: 0 }))
    .sort((a, b) => b.preventedPerCrew - a.preventedPerCrew || compareText(a.ward, b.ward))
    .map((entry, i) => ({ ...entry, rank: i + 1 }));
}
