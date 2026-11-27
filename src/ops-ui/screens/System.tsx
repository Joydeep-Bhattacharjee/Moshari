// System (PRD 7): offline status, provenance, scenario_id, parameters and honest deviations.
import { useSyncExternalStore } from "react";
import { Wifi, WifiOff } from "lucide-react";
import { canonicalJson } from "../../lib/ops/scenario.ts";
import type { ScreenProps } from "../screenProps";
import { Panel } from "../ui";

function subscribe(callback: () => void): () => void {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

const DEVIATIONS = [
  "Supply rounding is half down, not the PRD's half up: the dataset rounds every exact .5 down (1,197 bed rows prove it), so the formulas match all 31,320 rows.",
  "When the equity floors do not fit in the stock they are shared by Webster rounding, not largest remainder, which can give a ward more when stock falls (Alabama paradox).",
  "The 10% bed buffer is rounded down to whole beds, so a 1–9 bed ward keeps every bed usable; the PRD's floor(0.9 × capacity) blocked almost all routing.",
  "The crew effect comes from the 2- and 3-week Poisson models, whose water-logging coefficients are positive; the 4-week tree model and the P90 models keep their baselines.",
  "Bed capacity is a proxy (P75 of each ward's training-period bed need, 1–5 beds) and the crew pool default of 20 is an assumption; both are labelled where shown.",
  "The 2-week model over-forecasts the 2025 peak (901 forecast vs 373 actual for 2025-07-07); it is shown as is, next to the actual.",
];

type Props = ScreenProps & { elapsedMs: number };

export function System({ run, config, forecasts, scenario, elapsedMs }: Props) {
  const online = useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
  const c = config.constants;
  const p = config.provenance;
  const cutoffs = Object.entries(c.thresholds)
    .map(([h, t]) => `${h}w: ${t.map((v) => (v * c.decision_scale[h]).toFixed(1)).join("/")}`)
    .join(" · ");
  const params: [string, string][] = [
    ["Saline per case", `${c.supply_per_1000.saline_bags_needed / 1000}, round half down`],
    ["Test kits per case", `${c.supply_per_1000.diagnostic_kits_needed / 1000}, round half down`],
    ["Beds per case", `${c.supply_per_1000.hospital_beds_required / 1000}, peak week`],
    ["Priority", `${c.weights.risk}·risk + ${c.weights.density}·density + ${c.weights.cases}·cases`],
    ["Risk weight by tier", c.risk_norm.join(" / ")],
    ["Tier cut-offs (cases/wk)", cutoffs],
    ["Critical alert", `fill < ${c.critical_fill * 100}%, or High+ risk and fill < ${c.high_risk_fill * 100}%`],
    ["Crews per ward", `${c.crews_by_tier.join("/")} by tier, +1 if water-logging ≥ ${c.poor_drainage_from}`],
    ["Crew effect (r_max)", Object.entries(c.bands).map(([b, r]) => `${b} ${r}`).join(" · ")],
    ["Saturation / ramp", `c_sat ${c.crew_saturation} · ramp ${Object.values(c.ramp_by_week).join("/")}`],
    ["Water-logging floor", String(c.waterlog_floor)],
    ["Bed buffer", `${c.buffer_pct}% of beds, rounded down`],
  ];
  return (
    <>
      <div className="ops-grid-even">
        <Panel title="Offline status">
          <p className={`offline-chip ${online ? "" : "offline"}`}>
            {online ? <Wifi size={14} /> : <WifiOff size={14} />}
            {online ? "Browser online — not needed" : "Browser offline — everything still works"}
          </p>
          <p className="ops-note">
            All data ships with the site: <code>config.json</code> and <code>forecasts.json</code> (
            {forecasts.asof_weeks.length} as-of weeks); fonts and charts are bundled; every number is recomputed in
            this browser ({elapsedMs.toFixed(1)} ms for the last change). No request leaves the page. In Python,{" "}
            <code>make offline-check</code> rebuilds the committed export pack with sockets blocked, and the forecast
            falls back model → cached forecast → seasonal baseline.
          </p>
        </Panel>
        <Panel title="Provenance">
          <div className="param-grid">
            <div>
              <span>Scenario</span>
              <code>{run.scenarioId}</code>
            </div>
            <div>
              <span>Data hash (onsite CSV)</span>
              <code>{p.data_hash}</code>
            </div>
            <div>
              <span>Code commit</span>
              <code>{p.git_commit}</code>
            </div>
            <div>
              <span>Model trained</span>
              <code>{p.model_trained_at.slice(0, 10)}</code>
            </div>
            <div>
              <span>Training data ends</span>
              <code>{p.train_end}</code>
            </div>
            <div>
              <span>Forecast source</span>
              <code>cached model forecast</code>
            </div>
          </div>
          <p className="ops-note">scenario_id = first 8 characters of sha1(settings + data hash + commit):</p>
          <div className="formula">{canonicalJson(scenario)}</div>
        </Panel>
      </div>
      <Panel title="Parameters" subtitle="Read from the Python modules when the dashboard data is exported">
        <div className="param-grid">
          {params.map(([name, value]) => (
            <div key={name}>
              <span>{name}</span>
              <code>{value}</code>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Where we differ from the PRD, and why">
        <ul className="deviation-list">
          {DEVIATIONS.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
        <p className="ops-note">
          Model accuracy (holdout and backtests) is on the{" "}
          <a className="ops-link" href="#/forecast">
            Phase 1 forecast dashboard
          </a>
          , Validation tab.
        </p>
      </Panel>
    </>
  );
}
