"""SMS and WhatsApp renderings of a Notice (PRD 6.4). Deterministic plain templates.

SMS uses only the GSM 7-bit alphabet, and avoids its extension characters ([ ] | { } ...),
which cost two characters each. A ward with nothing to do fits one 160-character segment;
a ward with a deficit or a transfer instruction may use up to 3 segments (153 each).
Counterpart wards are written as W16: transfers never leave the city, so it is unambiguous.
"""
from __future__ import annotations

import math

from src.ops.notices import Notice, actions, plural

GSM_BASIC = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_EXTENSION = frozenset("^{}\\[~]|€\f")
SINGLE_SEGMENT_CHARS = 160
MULTI_SEGMENT_CHARS = 153
CITY_SHORT = {
    "Dhaka North": "DhakaN",
    "Dhaka South": "DhakaS",
    "Chattogram": "Ctg",
    "Gazipur": "Gazipur",
    "Narayanganj": "Ngonj",
}


def gsm_length(text: str) -> int:
    """Length in GSM 7-bit septets; raises for characters outside the GSM alphabet."""
    outside = sorted({c for c in text if c not in GSM_BASIC and c not in GSM_EXTENSION})
    if outside:
        raise ValueError(f"characters outside the GSM 7-bit alphabet: {outside[:5]}")
    return sum(2 if c in GSM_EXTENSION else 1 for c in text)


def sms_segments(text: str) -> int:
    length = gsm_length(text)
    return 1 if length <= SINGLE_SEGMENT_CHARS else math.ceil(length / MULTI_SEGMENT_CHARS)


def short_ward(ward_id: str) -> str:
    return "W" + ward_id.rsplit("_", 1)[-1]


def render_sms(n: Notice) -> str:
    parts = [
        f"DENGUE {n.asof} {n.ward_id} {CITY_SHORT.get(n.city, n.city)} {n.risk.upper()} "
        f"{n.cases_p50}c/wk (P90 {n.cases_p90})",
        f"Saline {n.saline_allocated}/{n.saline_required}",
        f"Kits {n.kits_allocated}/{n.kits_required}",
        f"Beds {n.beds_required}/cap{n.beds_capacity}",
        f"Crews {n.crews}",
    ]
    if n.deficit:
        parts.append("DEFICIT")
    parts += [f"Send {k}>{short_ward(ward)}" for ward, k in n.sends]
    parts += [f"Recv {k}<{short_ward(ward)}" for ward, k in n.receives]
    if n.unplaced:
        parts.append(f"Escalate {n.unplaced}pt")
    parts.append(f"ID {n.scenario_id} {n.generated_at}")
    return "; ".join(parts)


def overflow_text(n: Notice) -> str:
    parts = [f"Send {plural(k, 'patient')} to {ward}" for ward, k in n.sends]
    parts += [f"Receive {plural(k, 'patient')} from {ward}" for ward, k in n.receives]
    if n.unplaced:
        parts.append(f"{plural(n.unplaced, 'patient')} unplaced: escalate")
    return "; ".join(parts) or "none"


def _short_note(short: int) -> str:
    return f" (DEFICIT {short})" if short > 0 else ""


def render_whatsapp(n: Notice) -> str:
    first, last = n.weeks[0].target_week, n.weeks[-1].target_week
    lines = [
        f"*DENGUE ALERT · {n.ward_id} ({n.city})*",
        f"Risk: *{n.risk.upper()}* · Forecast {n.cases_p50} cases/wk (P90 {n.cases_p90}), {first} to {last}",
        "",
        "*Supplies (allocated / required)*",
        f"• Saline: {n.saline_allocated} / {n.saline_required} bags{_short_note(n.saline_short)}",
        f"• Test kits: {n.kits_allocated} / {n.kits_required}{_short_note(n.kits_short)}",
        f"• Beds: {n.beds_required} needed / {n.beds_capacity} capacity ({n.capacity_source})",
        "",
        f"*Spray crews:* {n.crews}",
        f"*Overflow:* {overflow_text(n)}",
        "",
        "*Actions*",
        *(f"{i}. {step}" for i, step in enumerate(actions(n), start=1)),
        "",
        f"_As of {n.asof} · Scenario {n.scenario_id} · {n.generated_at}_",
    ]
    return "\n".join(lines)
