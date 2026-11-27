"""Printable A4 ward brief (PRD 6.4): self-contained HTML, print to PDF from any browser.

No web fonts, scripts or images: the forecast band chart is inline SVG, so the brief
renders offline. Every value is HTML-escaped.
"""
from __future__ import annotations

import math
from html import escape

from src.ops.dispatch_text import overflow_text
from src.ops.notices import Notice, WeekBand, actions, display_cases

CHART_W, CHART_H, CHART_PAD = 520, 170, 34
RISK_COLOURS = ("#2f7d4f", "#b7791f", "#c2410c", "#9b1c1c")  # Low, Medium, High, Critical
SHORT_CLASS = ' class="short"'

STYLE = """
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
"""


def fmt1(value: float) -> str:
    """One decimal, rounded half up as floor(x * 10 + 0.5) / 10, so the TypeScript port
    (Math.floor) prints the same digits; format() alone rounds exact ties to even."""
    return f"{math.floor(value * 10 + 0.5) / 10:.1f}"


def band_chart(weeks: tuple[WeekBand, ...]) -> str:
    """Inline SVG: P10-P90 band, expected line, actual cases as dark dots."""
    top = max([w.p90 for w in weeks] + [w.actual or 0.0 for w in weeks] + [1.0])
    span = CHART_W - 2 * CHART_PAD
    xs = [CHART_PAD + span * (i / (len(weeks) - 1) if len(weeks) > 1 else 0.5) for i in range(len(weeks))]

    def y(value: float) -> float:
        return CHART_H - CHART_PAD - (CHART_H - 2 * CHART_PAD) * value / top

    upper = [f"{fmt1(x)},{fmt1(y(w.p90))}" for x, w in zip(xs, weeks)]
    lower = [f"{fmt1(x)},{fmt1(y(w.p10))}" for x, w in zip(reversed(xs), reversed(weeks))]
    line = " ".join(f"{fmt1(x)},{fmt1(y(w.expected))}" for x, w in zip(xs, weeks))
    points = "".join(f'<circle class="point" cx="{fmt1(x)}" cy="{fmt1(y(w.expected))}" r="3"/>' for x, w in zip(xs, weeks))
    actuals = "".join(
        f'<circle class="actual" cx="{fmt1(x)}" cy="{fmt1(y(w.actual))}" r="4"/>'
        for x, w in zip(xs, weeks)
        if w.actual is not None
    )
    labels = "".join(
        f'<text x="{fmt1(x)}" y="{CHART_H - 10}" text-anchor="middle">{escape(w.target_week)}</text>'
        for x, w in zip(xs, weeks)
    )
    return (
        f'<svg viewBox="0 0 {CHART_W} {CHART_H}" width="{CHART_W}" height="{CHART_H}" role="img" '
        f'aria-label="Weekly forecast band">'
        f'<polygon class="band" points="{" ".join(upper + lower)}"/>'
        f'<polyline class="line" points="{line}"/>{points}{actuals}{labels}'
        f'<text x="{CHART_PAD}" y="14">{display_cases(top)} cases/wk</text>'
        f'<text x="{CHART_W - CHART_PAD}" y="14" text-anchor="end">band P10-P90 · line expected · dot actual</text>'
        "</svg>"
    )


def _supply_rows(n: Notice) -> str:
    def row(name: str, required: int, allocated: int) -> str:
        short = required - allocated
        cls = SHORT_CLASS if short > 0 else ""
        return f"<tr><td>{name}</td><td>{required}</td><td>{allocated}</td><td{cls}>{short}</td></tr>"

    beds_cls = SHORT_CLASS if n.unplaced else ""
    return (
        row("Saline bags", n.saline_required, n.saline_allocated)
        + row("Test kits", n.kits_required, n.kits_allocated)
        + f"<tr><td>Hospital beds (capacity {n.beds_capacity}, {escape(n.capacity_source)})</td>"
        f"<td>{n.beds_required}</td><td>{n.beds_required - n.unplaced}</td><td{beds_cls}>{n.unplaced}</td></tr>"
    )


def render_brief(n: Notice) -> str:
    e = escape
    risk_badge = f'<span class="badge" style="background:{RISK_COLOURS[n.risk_rank]}">{e(n.risk.upper())}</span>'
    deficit_badge = '<span class="badge deficit">DEFICIT</span>' if n.deficit else ""
    first, last = n.weeks[0].target_week, n.weeks[-1].target_week
    steps = "".join(f"<li>{e(step)}</li>" for step in actions(n))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dengue brief · {e(n.ward_id)}</title><style>{STYLE}</style></head>
<body>
<header>
<h1>{e(n.ward_id)} <span class="city">{e(n.city)}</span></h1>
<p>{risk_badge}{deficit_badge}</p>
<p class="meta">As of {e(n.asof)} · Scenario {e(n.scenario_id)} · Generated {e(n.generated_at)}</p>
</header>
<h2>Forecast</h2>
<p>Peak {n.cases_p50} cases per week (P90 {n.cases_p90}) between {e(first)} and {e(last)}.</p>
{band_chart(n.weeks)}
<h2>Supplies</h2>
<table><thead><tr><th>Item</th><th>Required</th><th>Allocated</th><th>Short</th></tr></thead>
<tbody>{_supply_rows(n)}</tbody></table>
<h2>Spray crews</h2>
<p>{n.crews} crews assigned to this ward.</p>
<h2>Overflow</h2>
<p>{e(overflow_text(n))}</p>
<h2>Actions</h2>
<ol>{steps}</ol>
<footer>Prepared by DengueOps (Moshari) from scenario {e(n.scenario_id)}. Supply numbers use the dataset's own
formulas; bed capacity is a {e(n.capacity_source)} proxy.<br>Approved by: ______________________ Date: ____________</footer>
</body></html>
"""
