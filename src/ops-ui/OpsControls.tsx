// Sidebar controls for the Operations app: every Scenario setting, validated by range.
import type { CSSProperties } from "react";
import { CalendarDays, ChevronDown, Clock3, Package, RotateCcw, Settings2, ShieldCheck, Users } from "lucide-react";
import type { Band, Confidence, CrewMode, OpsConfig, Scenario } from "../lib/ops/types.ts";
import { Segmented } from "./ui";

const MAX_CREWS_TOTAL = 200;
const FLOOR_MAX = 50;

type Props = {
  scenario: Scenario;
  config: OpsConfig;
  asofWeeks: string[];
  onChange: (patch: Partial<Scenario>) => void;
};

function rangeStyle(value: number, low: number, high: number): CSSProperties {
  return { "--range": `${((value - low) / (high - low)) * 100}%` } as CSSProperties;
}

export function OpsControls({ scenario, config, asofWeeks, onChange }: Props) {
  const [stockLow, stockHigh] = config.constants.stock_pct_range;
  const latestFirst = [...asofWeeks].reverse();
  const clampCrews = (value: number) => Math.min(Math.max(Math.round(value) || 0, 0), MAX_CREWS_TOTAL);
  return (
    <div className="sidebar-controls">
      <div className="section-eyebrow">
        Scenario
        <Settings2 size={13} />
      </div>

      <label className="control-label" htmlFor="asof">
        <CalendarDays size={14} />
        As-of week
      </label>
      <div className="select-wrap">
        <select id="asof" value={scenario.asof} onChange={(e) => onChange({ asof: e.target.value })}>
          {latestFirst.map((w) => (
            <option key={w} value={w}>
              {w}
              {w === config.constants.defaults.asof ? " · 2025 peak" : ""}
            </option>
          ))}
        </select>
        <ChevronDown size={14} />
      </div>

      <label className="control-label">
        <Clock3 size={14} />
        Planning window
      </label>
      <Segmented
        label="Planning window"
        value={scenario.weeks}
        options={[1, 2, 3, 4].map((w) => ({ value: w, label: `${w} wk` }))}
        onChange={(weeks) => onChange({ weeks })}
      />

      <label className="control-label">
        <ShieldCheck size={14} />
        Planning confidence
      </label>
      <Segmented<Confidence>
        label="Planning confidence"
        value={scenario.confidence}
        options={[
          { value: "likely", label: "Likely" },
          { value: "bad", label: "Bad case P90" },
        ]}
        onChange={(confidence) => onChange({ confidence })}
      />

      <div className="sidebar-divider" />
      <div className="ops-sidebar-row">
        <label className="control-label" htmlFor="stock">
          <Package size={14} />
          Stock on hand
        </label>
        <span className="ops-slider-value">
          {scenario.stock_pct}
          <small>% of need</small>
        </span>
      </div>
      <input
        id="stock"
        type="range"
        min={stockLow}
        max={stockHigh}
        step={5}
        value={scenario.stock_pct}
        onChange={(e) => onChange({ stock_pct: Number(e.target.value) })}
        style={rangeStyle(scenario.stock_pct, stockLow, stockHigh)}
      />
      <div className="ops-sidebar-row">
        <label className="control-label" htmlFor="floor">
          Equity floor
        </label>
        <span className="ops-slider-value">
          {scenario.floor_pct}
          <small>% min per ward</small>
        </span>
      </div>
      <input
        id="floor"
        type="range"
        min={0}
        max={FLOOR_MAX}
        step={5}
        value={scenario.floor_pct}
        onChange={(e) => onChange({ floor_pct: Number(e.target.value) })}
        style={rangeStyle(scenario.floor_pct, 0, FLOOR_MAX)}
      />

      <div className="sidebar-divider" />
      <label className="control-label" htmlFor="crews">
        <Users size={14} />
        Spray crews available
      </label>
      <input
        id="crews"
        className="ops-number"
        type="number"
        min={0}
        max={MAX_CREWS_TOTAL}
        value={scenario.crews_total}
        onChange={(e) => onChange({ crews_total: clampCrews(Number(e.target.value)) })}
      />
      <Segmented<CrewMode>
        label="Crew plan"
        value={scenario.crew_mode}
        options={[
          { value: "priority", label: "By priority" },
          { value: "roi", label: "Optimize by ROI" },
        ]}
        onChange={(crew_mode) => onChange({ crew_mode })}
      />
      <Segmented<Band>
        label="Crew effectiveness band"
        value={scenario.band}
        options={[
          { value: "low", label: "Low" },
          { value: "base", label: "Base" },
          { value: "high", label: "High" },
        ]}
        onChange={(band) => onChange({ band })}
      />
      <label className="ops-check">
        <input
          type="checkbox"
          checked={scenario.apply_intervention}
          onChange={(e) => onChange({ apply_intervention: e.target.checked })}
        />
        Plan supplies and beds on the forecast after spraying
      </label>
      <button type="button" className="reset-button" onClick={() => onChange(config.constants.defaults)}>
        <RotateCcw size={12} />
        Reset to defaults
      </button>
    </div>
  );
}
