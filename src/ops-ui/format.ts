// Display helpers for the Operations screens.
import type { Alert, Resource } from "../lib/ops/types.ts";
import { KITS, SALINE } from "../lib/ops/types.ts";

export const fmtInt = (n: number): string => Math.round(n).toLocaleString("en-US");
export const fmt1 = (n: number): string =>
  n.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
export const fmtPct = (x: number): string => `${Math.round(x * 100)}%`;
/** Percent with one decimal below 10%, so small effects do not read as 0%. */
export const fmtPctFine = (x: number): string => (x < 0.1 ? `${(x * 100).toFixed(1)}%` : fmtPct(x));
export const sum = (values: number[]): number => values.reduce((s, v) => s + v, 0);

export const RESOURCE_LABEL: Record<Resource, string> = { [SALINE]: "Saline bags", [KITS]: "Test kits" };

const ALERT_RANK: Record<Alert, number> = { OK: 0, WARNING: 1, CRITICAL: 2 };
export function worstAlert(alerts: Alert[]): Alert {
  return alerts.reduce<Alert>((worst, a) => (ALERT_RANK[a] > ALERT_RANK[worst] ? a : worst), "OK");
}

export const ALERT_COLOR: Record<Alert, string> = { OK: "#15803d", WARNING: "#b45309", CRITICAL: "#b91c1c" };

/** Local time as "YYYY-MM-DD HH:MM", the timestamp format the notices use. */
export function nowStamp(date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function downloadBlob(name: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

/** CSV cell: quote when needed, double inner quotes. */
export function csvCell(value: string | number | boolean): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}
