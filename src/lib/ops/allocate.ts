// Constrained allocation (mirror of src/ops/allocate.py): equity floor (Webster-sequential
// when floors do not fit), then priority greedy, which equals the LP optimum.
import { argmax, compareText } from "./numeric.ts";
import type { Alert, AllocationRow, DemandRow, OpsConstants, Resource } from "./types.ts";
import { KITS, SALINE } from "./types.ts";

export const ALLOCATED: Resource[] = [SALINE, KITS];
const UNITS: Record<Resource, [string, string]> = { [SALINE]: ["saline", "bags"], [KITS]: ["kits", "kits"] };

export interface Ranked extends DemandRow {
  riskNorm: number;
  densityNorm: number;
  casesNorm: number;
  priority: number;
  priorityRank: number;
}

function checkPct(name: string, value: number, low: number, high: number): number {
  if (!Number.isInteger(value) || value < low || value > high) {
    throw new Error(`${name} must be a whole number from ${low} to ${high}, got ${value}`);
  }
  return value;
}

export function priorityScores(demand: DemandRow[], c: OpsConstants, densityRef: number): Ranked[] {
  const maxCases = Math.max(...demand.map((d) => d.cases));
  const scored = demand.map((d) => {
    const riskNorm = c.risk_norm[d.riskRank];
    const densityNorm = d.density / densityRef;
    const casesNorm = maxCases > 0 ? d.cases / maxCases : 0;
    const priority = c.weights.risk * riskNorm + c.weights.density * densityNorm + c.weights.cases * casesNorm;
    return { ...d, riskNorm, densityNorm, casesNorm, priority, priorityRank: 0 };
  });
  const order = [...scored].sort((a, b) => b.priority - a.priority || compareText(a.ward, b.ward));
  const rank = new Map(order.map((d, i) => [d.ward, i + 1]));
  return scored.map((d) => ({ ...d, priorityRank: rank.get(d.ward)! }));
}

export function stockUnits(totalNeed: number, stockPct: number, c: OpsConstants): number {
  const pct = checkPct("stock_pct", stockPct, c.stock_pct_range[0], c.stock_pct_range[1]);
  return Math.floor((pct * totalNeed) / 100);
}

export function equityFloors(need: number[], floorPct: number): number[] {
  const pct = checkPct("floor_pct", floorPct, 0, 100);
  return need.map((n) => Math.floor((pct * n + 99) / 100));
}

function fitFloors(floors: number[], stock: number): number[] {
  if (floors.reduce((s, f) => s + f, 0) <= stock) return floors;
  const given = floors.map(() => 0);
  for (let unit = 0; unit < stock; unit++) {
    const quotient = floors.map((f, i) => (given[i] < f ? f / (given[i] + 0.5) : -Infinity));
    given[argmax(quotient)] += 1;
  }
  return given;
}

export function greedyFill(capacity: number[], budget: number): number[] {
  let usedBefore = 0;
  return capacity.map((cap) => {
    const take = Math.min(Math.max(budget - usedBefore, 0), cap);
    usedBefore += cap;
    return take;
  });
}

/** (floors, allocation) for wards in priority order; the allocation sums to stock. */
export function allocateUnits(need: number[], stock: number, floorPct: number): [number[], number[]] {
  const total = need.reduce((s, n) => s + n, 0);
  if (stock < 0 || stock > total) throw new Error(`stock must be from 0 to total need ${total}, got ${stock}`);
  const floors = fitFloors(equityFloors(need, floorPct), stock);
  const used = floors.reduce((s, f) => s + f, 0);
  const topUp = greedyFill(need.map((n, i) => n - floors[i]), stock - used);
  return [floors, floors.map((f, i) => f + topUp[i])];
}

export function alertLevel(fill: number, riskRank: number, c: OpsConstants): Alert {
  const critical = fill < c.critical_fill || (riskRank >= c.high_risk_from && fill < c.high_risk_fill);
  if (critical) return "CRITICAL";
  return fill < 1 ? "WARNING" : "OK";
}

export function allocate(
  demand: DemandRow[],
  stockPct: number,
  floorPct: number,
  densityRef: number,
  c: OpsConstants,
): AllocationRow[] {
  const ranked = [...priorityScores(demand, c, densityRef)].sort((a, b) => a.priorityRank - b.priorityRank);
  return ALLOCATED.flatMap((resource) => {
    const need = ranked.map((d) => (resource === SALINE ? d.saline : d.kits));
    const total = need.reduce((s, n) => s + n, 0);
    const [floors, alloc] = allocateUnits(need, stockUnits(total, stockPct, c), floorPct);
    return ranked.map((d, i) => {
      const fill = need[i] > 0 ? alloc[i] / need[i] : 1;
      return {
        ward: d.ward,
        city: d.city,
        resource,
        priority: d.priority,
        priorityRank: d.priorityRank,
        riskRank: d.riskRank,
        need: need[i],
        floor: floors[i],
        allocated: alloc[i],
        fill,
        deficit: need[i] - alloc[i],
        alert: alertLevel(fill, d.riskRank, c),
      };
    });
  });
}

export interface ResourceTotals {
  need: number;
  allocated: number;
  short: number;
}

export interface RegionSummary {
  critical_wards: number;
  resources: Record<string, ResourceTotals>;
  banner: string;
}

export function regionSummary(rows: AllocationRow[]): RegionSummary {
  const resources: Record<string, ResourceTotals> = {};
  for (const resource of ALLOCATED) {
    const part = rows.filter((r) => r.resource === resource);
    if (part.length === 0) continue;
    resources[resource] = {
      need: part.reduce((s, r) => s + r.need, 0),
      allocated: part.reduce((s, r) => s + r.allocated, 0),
      short: part.reduce((s, r) => s + r.deficit, 0),
    };
  }
  const critical = new Set(rows.filter((r) => r.alert === "CRITICAL").map((r) => r.ward)).size;
  const shortfalls = Object.entries(resources).map(
    ([r, t]) => `${UNITS[r as Resource][0]} short ${t.short.toLocaleString("en-US")} ${UNITS[r as Resource][1]}`,
  );
  return { critical_wards: critical, resources, banner: [`${critical} wards critical`, ...shortfalls].join(" · ") };
}
