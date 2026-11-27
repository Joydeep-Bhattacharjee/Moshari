// Small shared pieces for the Operations screens, built on the Phase 1 card styles.
import type { ReactNode } from "react";
import { Badge, CardHeader } from "../components/DashboardUI";
import type { Tier } from "../data";
import type { Alert } from "../lib/ops/types.ts";

const TIER_NAMES: Tier[] = ["Low", "Medium", "High", "Critical"];

export function TierBadge({ rank, small = true }: { rank: number; small?: boolean }) {
  return <Badge tier={TIER_NAMES[rank]} small={small} />;
}

export function AlertPill({ alert }: { alert: Alert | "CITY_SATURATED" }) {
  const label = alert === "CITY_SATURATED" ? "SATURATED" : alert;
  const kind = alert === "OK" ? "ok" : alert === "WARNING" ? "warning" : "critical";
  return <span className={`alert-pill ${kind}`}>{label}</span>;
}

type KpiProps = { label: string; value: ReactNode; note?: ReactNode; tone?: "teal" | "orange" | "red" | "gray" };

export function Kpi({ label, value, note, tone = "teal" }: KpiProps) {
  return (
    <section className={`card kpi ops-kpi tone-${tone}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {note && <p>{note}</p>}
    </section>
  );
}

type SegmentedProps<T extends string | number> = {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
};

export function Segmented<T extends string | number>({ label, value, options, onChange }: SegmentedProps<T>) {
  return (
    <div className="horizon-switch ops-segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          className={o.value === value ? "selected" : ""}
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
        >
          {o.label}
          {o.value === value && <span />}
        </button>
      ))}
    </div>
  );
}

type PanelProps = { title: string; subtitle?: string; action?: ReactNode; className?: string; children: ReactNode };

export function Panel({ title, subtitle, action, className = "", children }: PanelProps) {
  return (
    <section className={`card ops-panel ${className}`}>
      <CardHeader title={title} subtitle={subtitle} action={action} />
      <div className="ops-panel-body">{children}</div>
    </section>
  );
}

export function FillBar({ fill, alert }: { fill: number; alert: Alert }) {
  return (
    <span className="fill-bar" aria-label={`${Math.round(fill * 100)}% supplied`}>
      <span className={`fill-${alert.toLowerCase()}`} style={{ width: `${Math.min(fill, 1) * 100}%` }} />
    </span>
  );
}
