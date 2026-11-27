// End-to-end decision chain for one Scenario (mirror of src/ops/pipeline.py):
// forecast window -> crew plan -> simulate -> post-intervention window -> demand ->
// allocation -> overflow routing. Pure and synchronous, so sliders recompute instantly.
import { allocate, priorityScores } from "./allocate.ts";
import { assignCrews, crewsNeeded } from "./crews.ts";
import { wardDemand } from "./demand.ts";
import { compareText } from "./numeric.ts";
import { routeOverflow } from "./overflow.ts";
import { scenarioErrors, scenarioId } from "./scenario.ts";
import { autoSuggest, intervenedWindow, preventedTable, simulate } from "./simulate.ts";
import type {
  AllocationRow,
  DemandRow,
  OpsConfig,
  OpsForecasts,
  Routing,
  Scenario,
  SimRow,
  WindowRow,
} from "./types.ts";

export interface ScenarioRun {
  scenario: Scenario;
  scenarioId: string;
  window: WindowRow[];
  crews: Map<string, number>;
  sim: SimRow[];
  planWindow: WindowRow[];
  demand: DemandRow[];
  allocation: AllocationRow[];
  routing: Routing;
}

export function addWeeks(isoDate: string, weeks: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 7 * weeks);
  return date.toISOString().slice(0, 10);
}

/** Cached forecast rows for weeks +1..+weeks, sorted by ward then week. */
export function windowRows(forecasts: OpsForecasts, config: OpsConfig, asof: string, weeks: number): WindowRow[] {
  const block = forecasts.windows[asof];
  if (!block) throw new Error(`no forecast for as-of week ${asof}`);
  const city = new Map(config.wards.map((w) => [w.id, w.city]));
  return Object.keys(block)
    .sort(compareText)
    .flatMap((ward) =>
      Array.from({ length: weeks }, (_, i) => {
        const k = i + 1;
        const w = block[ward];
        return {
          ward,
          city: city.get(ward)!,
          weekAhead: k,
          targetWeek: addWeeks(asof, k),
          modelHorizon: config.constants.window_plan[String(k)][1],
          expected: w.expected[i],
          p10: w.p10[i],
          p90: w.p90[i],
          tierRank: w.tier_rank[i],
          actual: w.actual[i],
          topDriver: forecasts.driver_labels[w.top_driver[i]],
        };
      }),
    );
}

export function rainByWard(forecasts: OpsForecasts, asof: string): Map<string, number> {
  return new Map(Object.entries(forecasts.windows[asof]).map(([ward, w]) => [ward, w.rain_sum]));
}

function crewPlan(
  s: Scenario,
  config: OpsConfig,
  window: WindowRow[],
  rain: Map<string, number>,
  densityRef: number,
): Map<string, number> {
  if (s.crew_mode === "roi") return autoSuggest(preventedTable(window, s.band, config, rain), s.crews_total);
  const c = config.constants;
  const ranked = priorityScores(wardDemand(window, s.confidence, config), c, densityRef).sort(
    (a, b) => a.priorityRank - b.priorityRank,
  );
  const need = ranked.map((d) => crewsNeeded(d.riskRank, d.waterlog, c));
  const plan = assignCrews(need, s.crews_total);
  return new Map(ranked.map((d, i) => [d.ward, plan[i]]));
}

export function runScenario(s: Scenario, config: OpsConfig, forecasts: OpsForecasts): ScenarioRun {
  const errors = scenarioErrors(s, config.constants, forecasts.asof_weeks);
  if (errors.length) throw new Error(`invalid scenario: ${errors.join("; ")}`);
  const c = config.constants;
  const densityRef = Math.max(...config.wards.map((w) => w.density));
  const rain = rainByWard(forecasts, s.asof);
  const window = windowRows(forecasts, config, s.asof, s.weeks);
  const crews = crewPlan(s, config, window, rain, densityRef);
  const sim = simulate(window, crews, s.band, config, rain);
  const planWindow = s.apply_intervention ? intervenedWindow(sim, c) : window;
  const demand = wardDemand(planWindow, s.confidence, config);
  const allocation = allocate(demand, s.stock_pct, s.floor_pct, densityRef, c);
  const priority = new Map<string, number>();
  for (const row of allocation) if (!priority.has(row.ward)) priority.set(row.ward, row.priority);
  const capacity = new Map(config.wards.map((w) => [w.id, w.capacity]));
  const routing = routeOverflow(
    demand.map((d) => ({
      ward: d.ward,
      city: d.city,
      beds: d.beds,
      capacity: capacity.get(d.ward)!,
      priority: priority.get(d.ward)!,
    })),
    c.buffer_pct,
  );
  return {
    scenario: s,
    scenarioId: scenarioId(s, config.provenance.data_hash, config.provenance.git_commit),
    window,
    crews,
    sim,
    planWindow,
    demand,
    allocation,
    routing,
  };
}
