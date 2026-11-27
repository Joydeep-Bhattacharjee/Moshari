// Allocation (PRD 6.1 / 7): equity floor + priority greedy per resource, live with the sliders.
import { useMemo, useState } from "react";
import type { Data } from "plotly.js";
import Chart from "../../components/Chart";
import { shortWard } from "../../lib/ops/dispatchText.ts";
import type { AllocationRow, Resource } from "../../lib/ops/types.ts";
import { KITS, SALINE } from "../../lib/ops/types.ts";
import { ALERT_COLOR, fmtInt, fmtPct, RESOURCE_LABEL, sum } from "../format";
import type { ScreenProps } from "../screenProps";
import { AlertPill, FillBar, Kpi, Panel, Segmented, TierBadge } from "../ui";

function initials(city: string): string {
  return city
    .split(" ")
    .map((w) => w[0])
    .join("");
}

function fillChart(rows: AllocationRow[]): Data[] {
  return [
    {
      x: rows.map((r) => `${shortWard(r.ward)} ${initials(r.city)}`),
      y: rows.map((r) => r.fill * 100),
      customdata: rows.map((r) => [r.ward, r.allocated, r.need]),
      type: "bar",
      marker: { color: rows.map((r) => ALERT_COLOR[r.alert]) },
      hovertemplate: "%{customdata[0]}<br>%{customdata[1]} of %{customdata[2]} (%{y:.0f}%)<extra></extra>",
    } as Data,
  ];
}

export function Allocation({ run, scenario, onExplain }: ScreenProps) {
  const [resource, setResource] = useState<Resource>(SALINE);
  const rows = useMemo(() => run.allocation.filter((r) => r.resource === resource), [run.allocation, resource]);
  const chart = useMemo(() => fillChart(rows), [rows]);
  const need = sum(rows.map((r) => r.need));
  const stock = sum(rows.map((r) => r.allocated));
  const floors = sum(rows.map((r) => r.floor));
  const unit = resource === SALINE ? "bags" : "kits";
  const basis = scenario.confidence === "bad" ? "bad case (P90)" : "likely case";
  return (
    <>
      <div className="ops-actions city-switch">
        <Segmented<Resource>
          label="Resource"
          value={resource}
          options={[
            { value: SALINE, label: RESOURCE_LABEL[SALINE] },
            { value: KITS, label: RESOURCE_LABEL[KITS] },
          ]}
          onChange={setResource}
        />
      </div>
      <div className="kpi-grid">
        <Kpi label={`${RESOURCE_LABEL[resource]} needed`} value={fmtInt(need)} note={`${scenario.weeks}-week window, ${basis}`} />
        <Kpi label="Stock available" value={fmtInt(stock)} note={`floor(${scenario.stock_pct}% × need)`} tone="gray" />
        <Kpi
          label="Short"
          value={
            <>
              {fmtInt(need - stock)}
              <small>{unit}</small>
            </>
          }
          tone={need > stock ? "red" : "gray"}
          note={`${rows.filter((r) => r.alert === "CRITICAL").length} wards critical`}
        />
        <Kpi
          label="Equity floors"
          value={fmtInt(floors)}
          tone="gray"
          note={`${scenario.floor_pct}% of each ward's need, rounded up`}
        />
      </div>
      <Panel title="Fill by ward, in priority order" subtitle="Red critical, amber warning, green fully supplied">
        <Chart
          data={chart}
          height={220}
          label={`${RESOURCE_LABEL[resource]} fill by ward`}
          layout={{
            yaxis: { range: [0, 105], ticksuffix: "%" },
            xaxis: { tickangle: -60, tickfont: { size: 8 } },
            margin: { l: 40, r: 10, t: 10, b: 60 },
          }}
        />
        <p className="ops-note">
          <strong>How it allocates:</strong> every ward first gets its equity floor, then stock goes to wards in
          priority order until it runs out. That greedy step is the exact optimum of the linear program max Σ
          priority × allocation (checked against the HiGHS solver in the tests). If the floors alone do not fit,
          they are shared by Webster rounding, so lowering stock never gives any ward more.
        </p>
      </Panel>
      <Panel title="Allocation table">
        <div className="ops-scroll">
          <table className="ops-table">
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Ward</th>
                <th>Risk</th>
                <th className="num">Priority</th>
                <th className="num">Need</th>
                <th className="num">Floor</th>
                <th className="num">Allocated</th>
                <th>Fill</th>
                <th className="num">Deficit</th>
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
                  <td>
                    <TierBadge rank={r.riskRank} />
                  </td>
                  <td className="num">{r.priority.toFixed(3)}</td>
                  <td className="num">{r.need}</td>
                  <td className="num">{r.floor}</td>
                  <td className="num">{r.allocated}</td>
                  <td>
                    <FillBar fill={r.fill} alert={r.alert} />
                    {fmtPct(r.fill)}
                  </td>
                  <td className={`num ${r.deficit ? "short" : ""}`}>{r.deficit}</td>
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
