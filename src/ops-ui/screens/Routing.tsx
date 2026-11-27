// Surge & Routing (PRD 6.2 / 7): same-city bed overflow, transfers and saturation.
import { useMemo, useState } from "react";
import type { Data } from "plotly.js";
import { TriangleAlert } from "lucide-react";
import Chart from "../../components/Chart";
import { shortWard } from "../../lib/ops/dispatchText.ts";
import type { RouteWard, Transfer } from "../../lib/ops/types.ts";
import { fmtInt, fmtPct } from "../format";
import type { ScreenProps } from "../screenProps";
import { AlertPill, Kpi, Panel, Segmented } from "../ui";

function bedsChart(wards: RouteWard[]): Data[] {
  const x = wards.map((w) => shortWard(w.ward));
  return [
    { x, y: wards.map((w) => w.required), type: "bar", name: "Beds needed", marker: { color: "#c2410c" } },
    { x, y: wards.map((w) => w.capacity), type: "bar", name: "Capacity (proxy P75)", marker: { color: "#cbd5e1" } },
  ];
}

function heatmap(wards: RouteWard[], transfers: Transfer[]): Data[] {
  const ids = wards.map((w) => w.ward);
  const patients = (from: string, to: string) =>
    transfers.filter((t) => t.fromWard === from && t.toWard === to).reduce((s, t) => s + t.patients, 0);
  return [
    {
      type: "heatmap",
      z: ids.map((from) => ids.map((to) => patients(from, to))),
      x: ids.map(shortWard),
      y: ids.map(shortWard),
      colorscale: [
        [0, "#f8fafc"],
        [1, "#0f766e"],
      ],
      showscale: false,
      hovertemplate: "from %{y} to %{x}: %{z} patients<extra></extra>",
    } as Data,
  ];
}

export function Routing({ run, onExplain }: ScreenProps) {
  const cities = run.routing.cities;
  const [picked, setPicked] = useState<string | null>(null);
  const city = picked ?? cities.find((c) => c.alert === "CITY_SATURATED")?.city ?? cities[0].city;
  const summary = cities.find((c) => c.city === city)!;
  const wards = useMemo(() => run.routing.wards.filter((w) => w.city === city), [run.routing.wards, city]);
  const transfers = useMemo(
    () => run.routing.transfers.filter((t) => t.city === city),
    [run.routing.transfers, city],
  );
  const beds = useMemo(() => bedsChart(wards), [wards]);
  const matrix = useMemo(() => heatmap(wards, transfers), [wards, transfers]);
  const flowNote =
    summary.moved === summary.maxFlow ? `= max-flow optimum (${summary.maxFlow}) ✓` : `max flow ${summary.maxFlow}`;
  return (
    <>
      <div className="city-switch">
        <Segmented
          label="City"
          value={city}
          options={cities.map((c) => ({ value: c.city, label: c.city }))}
          onChange={setPicked}
        />
      </div>
      {summary.alert === "CITY_SATURATED" && (
        <div className="ops-banner critical" role="status">
          <TriangleAlert size={16} />
          {city} is saturated: {summary.unplaced} patients have no bed after every same-city transfer. Escalate
          (field beds, regional request). Patients are never routed across cities.
        </div>
      )}
      <div className="kpi-grid">
        <Kpi label="Beds needed" value={fmtInt(summary.required)} note={`Peak week of the window, ${wards.length} wards`} />
        <Kpi
          label="Capacity"
          value={fmtInt(summary.capacity)}
          tone="gray"
          note={`${fmtInt(summary.usable)} usable after a 10% buffer · ${fmtPct(summary.utilizationPct / 100)} needed`}
        />
        <Kpi label="Patients moved" value={fmtInt(summary.moved)} tone="gray" note={flowNote} />
        <Kpi
          label="Unplaced"
          value={fmtInt(summary.unplaced)}
          tone={summary.unplaced ? "red" : "gray"}
          note={<AlertPill alert={summary.alert} />}
        />
      </div>
      <div className="ops-grid-2">
        <Panel title="Beds needed vs capacity" subtitle="Capacity is a proxy: P75 of each ward's historical bed need">
          <Chart
            data={beds}
            height={240}
            label={`Beds needed versus capacity in ${city}`}
            layout={{ barmode: "group", showlegend: true, legend: { orientation: "h", y: -0.2 } }}
          />
        </Panel>
        <Panel title="Transfer matrix" subtitle="Rows send, columns receive">
          {transfers.length ? (
            <Chart
              data={matrix}
              height={240}
              label={`Transfer matrix for ${city}`}
              layout={{ margin: { l: 40, r: 10, t: 10, b: 40 } }}
            />
          ) : (
            <p className="ops-note">
              No transfers in {city}:{" "}
              {summary.unplaced ? "no ward has spare beds to receive patients." : "no ward is over capacity."}
            </p>
          )}
        </Panel>
      </div>
      <Panel title="Transfers" subtitle="Deficit wards in priority order pull from the least-utilised wards first">
        <table className="ops-table">
          <thead>
            <tr>
              <th>From</th>
              <th>To</th>
              <th className="num">Patients</th>
            </tr>
          </thead>
          <tbody>
            {transfers.map((t) => (
              <tr key={`${t.fromWard}-${t.toWard}`} onClick={() => onExplain(t.fromWard)}>
                <td>{t.fromWard}</td>
                <td>{t.toWard}</td>
                <td className="num">{t.patients}</td>
              </tr>
            ))}
            {!transfers.length && (
              <tr>
                <td colSpan={3}>None</td>
              </tr>
            )}
          </tbody>
        </table>
      </Panel>
      <Panel title="Wards in the city">
        <table className="ops-table">
          <thead>
            <tr>
              <th>Ward</th>
              <th className="num">Needed</th>
              <th className="num">Capacity</th>
              <th className="num">Usable</th>
              <th className="num">Sent</th>
              <th className="num">Received</th>
              <th className="num">Unplaced</th>
              <th className="num">Load after</th>
            </tr>
          </thead>
          <tbody>
            {wards.map((w) => (
              <tr key={w.ward} className={w.unplaced ? "row-critical" : ""} onClick={() => onExplain(w.ward)}>
                <td>{w.ward}</td>
                <td className="num">{w.required}</td>
                <td className="num">{w.capacity}</td>
                <td className="num">{w.usable}</td>
                <td className="num">{w.sent}</td>
                <td className="num">{w.received}</td>
                <td className={`num ${w.unplaced ? "short" : ""}`}>{w.unplaced}</td>
                <td className="num">{fmtPct(w.utilizationAfter)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </>
  );
}
