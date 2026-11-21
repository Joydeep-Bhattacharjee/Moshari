import type { ReactNode } from "react";
import { TIER_COLORS, type Tier } from "../data";

export function Badge({ tier, small = false }: { tier: Tier; small?: boolean }) {
  const color = TIER_COLORS[tier];
  return (
    <span
      className={`risk-badge ${small ? "small" : ""}`}
      style={{ background: color.bg, color: color.text, borderColor: color.border }}
    >
      <span style={{ background: color.border }} aria-hidden="true" />
      {tier}
    </span>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="card-header">
      <div>
        <h3>{title}</h3>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
