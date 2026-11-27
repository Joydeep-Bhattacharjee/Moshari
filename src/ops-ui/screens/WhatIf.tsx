// What-If vector control (PRD 6.3 / 7): crews lower water-logging, the model's response
// gives cases prevented; ROI leaderboard and the auto-suggested plan.
import { useMemo } from "react";
import type { Data } from "plotly.js";
import Chart from "../../components/Chart";
import { supplyUnits, wardDemand } from "../../lib/ops/demand.ts";
import { rainByWard } from "../../lib/ops/pipeline.ts";
import { autoSuggest, intervenedWindow, preventedTable, roiLeaderboard } from "../../lib/ops/simulate.ts";
import type { DemandRow, SimRow } from "../../lib/ops/types.ts";
import { SALINE } from "../../lib/ops/types.ts";
import { fmt1, fmtInt, fmtPct, fmtPctFine, sum } from "../format";
import type { ScreenProps } from "../screenProps";
import { Kpi, Panel } from "../ui";

const CATEGORY_AXIS = { type: "category" as const, showgrid: false, fixedrange: true };

function weeklyCharts(sim: SimRow[], salinePer1000: number): [Data[], Data[]] {
  const weeks = [...new Set(sim.map((s) => s.targetWeek))].sort();
  const part = (w: string) => sim.filter((s) => s.targetWeek === w);
  const cases = (pick: (s: SimRow) => number) => weeks.map((w) => sum(part(w).map(pick)));
  const saline = (pick: (s: SimRow) => number) =>
    weeks.map((w) => sum(part(w).map((s) => supplyUnits(pick(s), salinePer1000))));
  const line = (name: string, y: number[], color: string, dash?: "dot") =>
    ({ x: weeks, y, name, type: "scatter", mode: "lines+markers", line: { color, width: 2.5, dash } }) as Data;
  const bar = (name: string, y: number[], color: string) =>
    ({ x: weeks, y, name, type: "bar", marker: { color } }) as Data;
  return [
    [
      line("No spraying", cases((s) => s.expected), "#c2410c"),
      line("With crews", cases((s) => s.expectedAfter), "#0f766e", "dot"),
    ],
    [
      bar("No spraying", saline((s) => s.expected), "#fdba74"),
      bar("With crews", saline((s) => s.expectedAfter), "#5eead4"),
    ],
  ];
}

export function WhatIf({ run, config, forecasts, scenario, onChange, onExplain }: ScreenProps) {
  const c = config.constants;
  const table = useMemo(
    () => preventedTable(run.window, scenario.band, config, rainByWard(forecasts, scenario.asof)),
    [run.window, scenario.band, scenario.asof, config, forecasts],
  );
  const board = useMemo(() => roiLeaderboard(table), [table]);
  const roiPlan = useMemo(() => autoSuggest(table, scenario.crews_total), [table, scenario.crews_total]);
  const [casesChart, salineChart] = useMemo(() => weeklyCharts(run.sim, c.supply_per_1000[SALINE]), [run.sim, c]);
  const value = (plan: Map<string, number>) => sum([...table.entries()].map(([w, v]) => v[plan.get(w) ?? 0]));
  const crewsUsed = sum([...run.crews.values()]);
  const prevented = sum(run.sim.map((s) => s.prevented));
  const baseline = sum(run.sim.map((s) => s.expected));
  const before = wardDemand(run.window, scenario.confidence, config);
  const after = wardDemand(intervenedWindow(run.sim, c), scenario.confidence, config);
  const avoided = (pick: (d: DemandRow) => number) => sum(before.map(pick)) - sum(after.map(pick));
  const differs = [...roiPlan.keys()].filter((w) => (roiPlan.get(w) ?? 0) !== (run.crews.get(w) ?? 0));
  const atFloor = config.wards.filter((w) => w.waterlog <= c.waterlog_floor).map((w) => w.id);
  const planNote = scenario.crew_mode === "roi" ? "Optimized by ROI" : "In priority order, up to each ward's need";
  return (
    <>
      <div className="kpi-grid">
        <Kpi label="Crews deployed" value={`${crewsUsed} / ${scenario.crews_total}`} note={planNote} />
        <Kpi
          label="Cases prevented"
          value={
            <>
              {fmt1(prevented)}
              <small>
                {fmtPctFine(baseline ? prevented / baseline : 0)} of {fmtInt(baseline)}
              </small>
            </>
          }
          note={`${scenario.weeks}-week window, ${scenario.band} effectiveness band`}
        />
        <Kpi
          label="Saline avoided"
          value={
            <>
              {fmtInt(avoided((d) => d.saline))}
              <small>bags</small>
            </>
          }
          tone="gray"
          note={`Kits ${fmtInt(avoided((d) => d.kits))} · beds ${fmtInt(avoided((d) => d.beds))}`}
        />
        <Kpi
          label="Prevented per crew"
          value={crewsUsed ? fmt1(prevented / crewsUsed) : "–"}
          tone="gray"
          note="cases over the window"
        />
      </div>
      <div className="ops-grid-even">
        <Panel title="Cases per week" subtitle="Week +1 is unchanged: spraying shows after 2–4 weeks">
          <Chart
            data={casesChart}
            height={220}
            label="Cases per week with and without crews"
            layout={{ showlegend: true, legend: { orientation: "h", y: -0.25 }, xaxis: CATEGORY_AXIS }}
          />
        </Panel>
        <Panel title="Saline bags per week" subtitle="Dataset formula applied to each week's forecast">
          <Chart
            data={salineChart}
            height={220}
            label="Saline bags per week with and without crews"
            layout={{ barmode: "group", showlegend: true, legend: { orientation: "h", y: -0.25 }, xaxis: CATEGORY_AXIS }}
          />
        </Panel>
      </div>
      <div className="ops-grid-even">
        <Panel title="ROI leaderboard" subtitle="Cases prevented over the window by one crew in each ward">
          <table className="ops-table">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Ward</th>
                <th className="num">Prevented / crew</th>
                <th className="num">Crews now</th>
              </tr>
            </thead>
            <tbody>
              {board.slice(0, 10).map((r) => (
                <tr key={r.ward} onClick={() => onExplain(r.ward)}>
                  <td className="num">{r.rank}</td>
                  <td>{r.ward}</td>
                  <td className="num">{r.preventedPerCrew.toFixed(2)}</td>
                  <td className="num">{run.crews.get(r.ward) ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel
          title="Recommended deployment"
          subtitle="Crews go one at a time to the largest marginal gain (optimal because returns diminish)"
          action={
            scenario.crew_mode !== "roi" && (
              <button type="button" className="ghost-button" onClick={() => onChange({ crew_mode: "roi" })}>
                Use this plan
              </button>
            )
          }
        >
          <p className="ops-note">
            Current plan prevents <strong>{fmt1(value(run.crews))}</strong> cases; the recommended plan prevents{" "}
            <strong>{fmt1(value(roiPlan))}</strong> with the same {scenario.crews_total} crews.
          </p>
          <table className="ops-table">
            <thead>
              <tr>
                <th>Ward</th>
                <th className="num">Current</th>
                <th className="num">Recommended</th>
              </tr>
            </thead>
            <tbody>
              {differs.slice(0, 12).map((w) => (
                <tr key={w} onClick={() => onExplain(w)}>
                  <td>{w}</td>
                  <td className="num">{run.crews.get(w) ?? 0}</td>
                  <td className="num">{roiPlan.get(w) ?? 0}</td>
                </tr>
              ))}
              {!differs.length && (
                <tr>
                  <td colSpan={3}>The current plan is already the recommended one.</td>
                </tr>
              )}
            </tbody>
          </table>
        </Panel>
      </div>
      <p className="ops-note">
        <strong>Read this as model-based sensitivity, not a causal estimate.</strong> Crews lower each ward's
        water-logging index (by at most {fmtPct(c.bands[scenario.band])}, with diminishing returns), and the forecast
        model is re-evaluated on the lowered index. The index is fixed per ward in the data, so its effect was learned
        across wards. {atFloor.length} wards ({atFloor.join(", ")}) already have the lowest index in the data, so no
        benefit is modelled for them.
      </p>
    </>
  );
}
