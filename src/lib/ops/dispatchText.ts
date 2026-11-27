// SMS and WhatsApp renderings of a Notice (mirror of src/ops/dispatch_text.py).
import { actions, plural } from "./notices.ts";
import type { Notice } from "./notices.ts";

const GSM_BASIC = new Set(
  "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?" +
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà",
);
const GSM_EXTENSION = new Set("^{}\\[~]|€\f");
const SINGLE_SEGMENT_CHARS = 160;
const MULTI_SEGMENT_CHARS = 153;
export const CITY_SHORT: Record<string, string> = {
  "Dhaka North": "DhakaN",
  "Dhaka South": "DhakaS",
  Chattogram: "Ctg",
  Gazipur: "Gazipur",
  Narayanganj: "Ngonj",
};

/** Length in GSM 7-bit septets; throws for characters outside the GSM alphabet. */
export function gsmLength(text: string): number {
  const chars = [...text];
  const outside = [...new Set(chars.filter((c) => !GSM_BASIC.has(c) && !GSM_EXTENSION.has(c)))];
  if (outside.length) throw new Error(`characters outside the GSM 7-bit alphabet: ${outside.slice(0, 5).join("")}`);
  return chars.reduce((sum, c) => sum + (GSM_EXTENSION.has(c) ? 2 : 1), 0);
}

export function smsSegments(text: string): number {
  const length = gsmLength(text);
  return length <= SINGLE_SEGMENT_CHARS ? 1 : Math.ceil(length / MULTI_SEGMENT_CHARS);
}

export function shortWard(wardId: string): string {
  return "W" + wardId.slice(wardId.lastIndexOf("_") + 1);
}

export function renderSms(n: Notice): string {
  const parts = [
    `DENGUE ${n.asof} ${n.wardId} ${CITY_SHORT[n.city] ?? n.city} ${n.risk.toUpperCase()} ` +
      `${n.casesP50}c/wk (P90 ${n.casesP90})`,
    `Saline ${n.salineAllocated}/${n.salineRequired}`,
    `Kits ${n.kitsAllocated}/${n.kitsRequired}`,
    `Beds ${n.bedsRequired}/cap${n.bedsCapacity}`,
    `Crews ${n.crews}`,
  ];
  if (n.deficit) parts.push("DEFICIT");
  for (const [ward, k] of n.sends) parts.push(`Send ${k}>${shortWard(ward)}`);
  for (const [ward, k] of n.receives) parts.push(`Recv ${k}<${shortWard(ward)}`);
  if (n.unplaced) parts.push(`Escalate ${n.unplaced}pt`);
  parts.push(`ID ${n.scenarioId} ${n.generatedAt}`);
  return parts.join("; ");
}

export function overflowText(n: Notice): string {
  const parts = [
    ...n.sends.map(([ward, k]) => `Send ${plural(k, "patient")} to ${ward}`),
    ...n.receives.map(([ward, k]) => `Receive ${plural(k, "patient")} from ${ward}`),
  ];
  if (n.unplaced) parts.push(`${plural(n.unplaced, "patient")} unplaced: escalate`);
  return parts.join("; ") || "none";
}

function shortNote(short: number): string {
  return short > 0 ? ` (DEFICIT ${short})` : "";
}

export function renderWhatsapp(n: Notice): string {
  const first = n.weeks[0].targetWeek;
  const last = n.weeks[n.weeks.length - 1].targetWeek;
  return [
    `*DENGUE ALERT · ${n.wardId} (${n.city})*`,
    `Risk: *${n.risk.toUpperCase()}* · Forecast ${n.casesP50} cases/wk (P90 ${n.casesP90}), ${first} to ${last}`,
    "",
    "*Supplies (allocated / required)*",
    `• Saline: ${n.salineAllocated} / ${n.salineRequired} bags${shortNote(n.salineShort)}`,
    `• Test kits: ${n.kitsAllocated} / ${n.kitsRequired}${shortNote(n.kitsShort)}`,
    `• Beds: ${n.bedsRequired} needed / ${n.bedsCapacity} capacity (${n.capacitySource})`,
    "",
    `*Spray crews:* ${n.crews}`,
    `*Overflow:* ${overflowText(n)}`,
    "",
    "*Actions*",
    ...actions(n).map((step, i) => `${i + 1}. ${step}`),
    "",
    `_As of ${n.asof} · Scenario ${n.scenarioId} · ${n.generatedAt}_`,
  ].join("\n");
}
