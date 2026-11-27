// Printable A4 ward brief (mirror of src/ops/brief.py): self-contained HTML, inline SVG
// chart, every value escaped. Must match Python byte for byte (parity test).
import { overflowText } from "./dispatchText.ts";
import { actions, displayCases } from "./notices.ts";
import type { Notice, WeekBand } from "./notices.ts";

const CHART_W = 520;
const CHART_H = 170;
const CHART_PAD = 34;
const RISK_COLOURS = ["#2f7d4f", "#b7791f", "#c2410c", "#9b1c1c"]; // Low, Medium, High, Critical
const SHORT_CLASS = ' class="short"';

const STYLE = `
@page { size: A4; margin: 16mm; }
* { box-sizing: border-box; }
body { font-family: Georgia, "Times New Roman", serif; color: #1c1917; margin: 0; line-height: 1.45; }
header { border-bottom: 3px solid #1c1917; padding-bottom: 10px; margin-bottom: 14px; }
h1 { font-size: 26px; margin: 0; letter-spacing: -0.01em; }
h1 .city { font-weight: normal; color: #57534e; font-size: 18px; }
h2 { font: 600 12px/1.2 system-ui, sans-serif; text-transform: uppercase; letter-spacing: 0.08em;
     color: #57534e; margin: 18px 0 6px; }
.badge { display: inline-block; font: 700 12px/1 system-ui, sans-serif; color: #fff; padding: 5px 9px;
         border-radius: 2px; margin-right: 6px; letter-spacing: 0.05em; }
.deficit { background: #1c1917; }
.meta { font: 12px system-ui, sans-serif; color: #57534e; margin: 8px 0 0; }
table { border-collapse: collapse; width: 100%; font: 13px system-ui, sans-serif; }
th, td { border-bottom: 1px solid #d6d3d1; padding: 6px 8px; text-align: right; }
th:first-child, td:first-child { text-align: left; }
td.short { color: #9b1c1c; font-weight: 700; }
svg text { font: 11px system-ui, sans-serif; fill: #57534e; }
.band { fill: #fde68a; } .line { fill: none; stroke: #9a3412; stroke-width: 2; }
.point { fill: #9a3412; } .actual { fill: #1c1917; }
ol { margin: 0; padding-left: 20px; }
footer { margin-top: 26px; border-top: 1px solid #d6d3d1; padding-top: 8px; font: 12px system-ui, sans-serif;
         color: #57534e; }
`;

/** Same output as Python's html.escape(text, quote=True). */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

/** One decimal, rounded half up as floor(x * 10 + 0.5) / 10, like Python's fmt1. */
export function fmt1(value: number): string {
  return (Math.floor(value * 10 + 0.5) / 10).toFixed(1);
}

export function bandChart(weeks: WeekBand[]): string {
  const top = Math.max(...weeks.map((w) => w.p90), ...weeks.map((w) => w.actual ?? 0), 1.0);
  const span = CHART_W - 2 * CHART_PAD;
  const xs = weeks.map((_, i) => CHART_PAD + span * (weeks.length > 1 ? i / (weeks.length - 1) : 0.5));
  const y = (value: number) => CHART_H - CHART_PAD - ((CHART_H - 2 * CHART_PAD) * value) / top;
  const upper = weeks.map((w, i) => `${fmt1(xs[i])},${fmt1(y(w.p90))}`);
  const lower = weeks.map((w, i) => `${fmt1(xs[i])},${fmt1(y(w.p10))}`).reverse();
  const line = weeks.map((w, i) => `${fmt1(xs[i])},${fmt1(y(w.expected))}`).join(" ");
  const points = weeks
    .map((w, i) => `<circle class="point" cx="${fmt1(xs[i])}" cy="${fmt1(y(w.expected))}" r="3"/>`)
    .join("");
  const actuals = weeks
    .map((w, i) => (w.actual === null ? "" : `<circle class="actual" cx="${fmt1(xs[i])}" cy="${fmt1(y(w.actual))}" r="4"/>`))
    .join("");
  const labels = weeks
    .map((w, i) => `<text x="${fmt1(xs[i])}" y="${CHART_H - 10}" text-anchor="middle">${escapeHtml(w.targetWeek)}</text>`)
    .join("");
  return (
    `<svg viewBox="0 0 ${CHART_W} ${CHART_H}" width="${CHART_W}" height="${CHART_H}" role="img" ` +
    `aria-label="Weekly forecast band">` +
    `<polygon class="band" points="${[...upper, ...lower].join(" ")}"/>` +
    `<polyline class="line" points="${line}"/>${points}${actuals}${labels}` +
    `<text x="${CHART_PAD}" y="14">${displayCases(top)} cases/wk</text>` +
    `<text x="${CHART_W - CHART_PAD}" y="14" text-anchor="end">band P10-P90 · line expected · dot actual</text>` +
    "</svg>"
  );
}

function supplyRows(n: Notice): string {
  const row = (name: string, required: number, allocated: number) => {
    const short = required - allocated;
    const cls = short > 0 ? SHORT_CLASS : "";
    return `<tr><td>${name}</td><td>${required}</td><td>${allocated}</td><td${cls}>${short}</td></tr>`;
  };
  const bedsCls = n.unplaced ? SHORT_CLASS : "";
  return (
    row("Saline bags", n.salineRequired, n.salineAllocated) +
    row("Test kits", n.kitsRequired, n.kitsAllocated) +
    `<tr><td>Hospital beds (capacity ${n.bedsCapacity}, ${escapeHtml(n.capacitySource)})</td>` +
    `<td>${n.bedsRequired}</td><td>${n.bedsRequired - n.unplaced}</td><td${bedsCls}>${n.unplaced}</td></tr>`
  );
}

export function renderBrief(n: Notice): string {
  const e = escapeHtml;
  const riskBadge = `<span class="badge" style="background:${RISK_COLOURS[n.riskRank]}">${e(n.risk.toUpperCase())}</span>`;
  const deficitBadge = n.deficit ? '<span class="badge deficit">DEFICIT</span>' : "";
  const first = n.weeks[0].targetWeek;
  const last = n.weeks[n.weeks.length - 1].targetWeek;
  const steps = actions(n)
    .map((step) => `<li>${e(step)}</li>`)
    .join("");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dengue brief · ${e(n.wardId)}</title><style>${STYLE}</style></head>
<body>
<header>
<h1>${e(n.wardId)} <span class="city">${e(n.city)}</span></h1>
<p>${riskBadge}${deficitBadge}</p>
<p class="meta">As of ${e(n.asof)} · Scenario ${e(n.scenarioId)} · Generated ${e(n.generatedAt)}</p>
</header>
<h2>Forecast</h2>
<p>Peak ${n.casesP50} cases per week (P90 ${n.casesP90}) between ${e(first)} and ${e(last)}.</p>
${bandChart(n.weeks)}
<h2>Supplies</h2>
<table><thead><tr><th>Item</th><th>Required</th><th>Allocated</th><th>Short</th></tr></thead>
<tbody>${supplyRows(n)}</tbody></table>
<h2>Spray crews</h2>
<p>${n.crews} crews assigned to this ward.</p>
<h2>Overflow</h2>
<p>${e(overflowText(n))}</p>
<h2>Actions</h2>
<ol>${steps}</ol>
<footer>Prepared by DengueOps (Moshari) from scenario ${e(n.scenarioId)}. Supply numbers use the dataset's own
formulas; bed capacity is a ${e(n.capacitySource)} proxy.<br>Approved by: ______________________ Date: ____________</footer>
</body></html>
`;
}
