// Command Overview (PRD 7): region KPIs, alert banner, forecast vs actual, ward table.
import { useMemo } from "react";
import type { Data } from "plotly.js";
import { CircleCheck, TriangleAlert } from "lucide-react";
import Chart from "../../components/Chart";
import { regionSummary } from "../../lib/ops/allocate.ts";
import type { ScenarioRun } from "../../lib/ops/pipeline.ts";
import { KITS, SALINE } from "../../lib/ops/types.ts";
import { fmtInt, fmtPct, sum } from "../format";
import { weeklyTotals, wardRows, type ScreenProps } from "../screenProps";
import { AlertPill, Kpi, Panel, TierBadge } from "../ui";

function forecastChart(run: ScenarioRun, showAfter: boolean): Data[] {
  const base = weeklyTotals(run.window);
  const after = weeklyTotals(run.planWindow);
  const x = base.map((w) => w.week);
  const traces: Data[] = [
    {
      x,
      y: base.map((w) => w.p90),
      type: "scatter",
      mode: "lines",
      line: { width: 0 },
      hoverinfo: "skip",
      showlegend: false,
    },
    {
      x,
      y: base.map((w) => w.p10),
      type: "scatter",
      mode: "lines",
      fill: "tonexty",
      fillcolor: "rgba(251, 191, 36, 0.25)",
      line: { width: 0 },
      name: "P10–P90 band",
      hoverinfo: "skip",
    },
    {
      x,
      y: base.map((w) => w.actual),
      type: "bar",
      width: 0.35,
      name: "Actual cases",
      marker: { color: "#cbd5e1" },
      hovertemplate: "%{x}<br>Actual %{y}<extra></extra>",
    },
    {
      x,
      y: base.map((w) => w.expected),
      type: "scatter",
      mode: "lines+markers",
      name: "Expected (likely)",
      line: { color: "#c2410c", width: 2.5 },
      hovertemplate: "%{x}<br>Expected %{y:.0f}<extra></extra>",
    },
  ];
  if (showAfter) {
    traces.push({
      x,
      y: after.map((w) => w.expected),
      type: "scatter",
      mode: "lines+markers",
      name: "After spraying",
      line: { color: "#0f766e", width: 2, dash: "dot" },
      hovertemplate: "%{x}<br>After spraying %{y:.0f}<extra></extra>",
    });
  }
  return traces;
}

export function Overview({ run, scenario, onExplain }: ScreenProps) {
  const summary = regionSummary(run.allocation);
  const rows = useMemo(() => wardRows(run), [run]);
  const cities = run.routing.cities;
  const unplaced = sum(cities.map((c) => c.unplaced));
  const saturated = cities.filter((c) => c.alert === "CITY_SATURATED").length;
  const utilisation = sum(cities.map((c) => c.required)) / sum(cities.map((c) => c.capacity));
  const highRisk = run.demand.filter((d) => d.riskRank >= 2).length;
  const showAfter = scenario.apply_intervention && sum([...run.crews.values()]) > 0;
  const chart = useMemo(() => forecastChart(run, showAfter), [run, showAfter]);
  const anyAlert = rows.some((r) => r.alert !== "OK");
  const kind = summary.critical_wards > 0 || unplaced > 0 ? "critical" : anyAlert ? "warning" : "ok";
  return (
    <>
      <div className={`ops-banner ${kind}`} role="status">
        {kind === "ok" ? <CircleCheck size={16} /> : <TriangleAlert size={16} />}
        {summary.banner}
        {unplaced > 0 && ` · ${fmtInt(unplaced)} patients without a bed`}
        <small>Scenario {run.scenarioId}</small>
      </div>
      <div className="kpi-grid">
        <Kpi
          label="Cases in window"
          value={
            <>
              {fmtInt(sum(run.planWindow.map((r) => r.expected)))}
              <small>P90 {fmtInt(sum(run.planWindow.map((r) => r.p90)))}</small>
            </>
          }
          note={`${scenario.weeks}-week window after ${scenario.asof}`}
        />
        <Kpi
          label="Critical wards"
          value={summary.critical_wards}
          tone={summary.critical_wards ? "red" : "gray"}
          note={`${highRisk} wards at High or Critical risk`}
        />
        <Kpi
          label="Saline short"
          value={
            <>
              {fmtInt(summary.resources[SALINE].short)}
              <small>bags</small>
            </>
          }
          tone={summary.resources[SALINE].short ? "orange" : "gray"}
          note={`Test kits short ${fmtInt(summary.resources[KITS].short)}`}
        />
        <Kpi
          label="Beds"
          value={
            <>
              {fmtInt(unplaced)}
              <small>unplaced</small>
            </>
          }
          tone={unplaced ? "red" : "gray"}
          note={`${saturated} of ${cities.length} cities saturated · ${fmtPct(utilisation)} of capacity needed`}
        />
      </div>
      <Panel
        title="Region forecast vs actual"
        subtitle="Sum over 60 wards per target week; actual bars show what happened (backtest)"
      >
        <Chart
          data={chart}
          height={230}
          label="Region forecast versus actual cases"
          layout={{
            showlegend: true,
            legend: { orientation: "h", y: -0.25 },
            xaxis: { type: "category", showgrid: false, fixedrange: true },
          }}
        />
      </Panel>
      <Panel title="Wards by priority" subtitle="Click a ward to see how every number was derived">
        <div className="ops-scroll">
          <table className="ops-table">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Ward</th>
                <th>City</th>
                <th>Risk</th>
                <th className="num">Cases</th>
                <th className="num">Saline</th>
                <th className="num">Kits</th>
                <th className="num">Beds / cap</th>
                <th className="num">Crews</th>
                <th>Alert</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.ward} className={`row-${r.alert.toLowerCase()}`} onClick={() => onExplain(r.ward)}>
                  <td className="num">{r.priorityRank}</td>
                  <td>
                    <button type="button" className="ward-link" onClick={() => onExplain(r.ward)}>
                      {r.ward}
                    </button>
                  </td>
                  <td>{r.city}</td>
                  <td>
                    <TierBadge rank={r.riskRank} />
                  </td>
                  <td className="num">{r.cases.toFixed(1)}</td>
                  <td className={`num ${r.salineAlloc < r.salineNeed ? "short" : ""}`}>
                    {r.salineAlloc}/{r.salineNeed}
                  </td>
                  <td className={`num ${r.kitsAlloc < r.kitsNeed ? "short" : ""}`}>
                    {r.kitsAlloc}/{r.kitsNeed}
                  </td>
                  <td className={`num ${r.unplaced ? "short" : ""}`}>
                    {r.beds}/{r.capacity}
                  </td>
                  <td className="num">{r.crews}</td>
                  <td>
                    <AlertPill alert={r.alert} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
