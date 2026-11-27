// Same-city overflow routing (mirror of src/ops/overflow.py).
// Every deficit ward reaches every donor in its city at equal cost, so the max flow is
// min(total deficit, total headroom); the greedy places exactly that.
import { argmin, compareText } from "./numeric.ts";
import type { CitySummary, RouteWard, Routing, Transfer } from "./types.ts";

export interface RouteInput {
  ward: string;
  city: string;
  beds: number;
  capacity: number;
  priority: number;
}

/** capacity - floor(capacity * buffer / 100): the buffer is whole beds, rounded down. */
export function usableCapacity(capacity: number, bufferPct: number): number {
  return capacity - Math.floor((capacity * bufferPct) / 100);
}

function routeCity(rows: RouteInput[], bufferPct: number): [Transfer[], RouteWard[]] {
  const req = rows.map((r) => r.beds);
  const cap = rows.map((r) => r.capacity);
  const usable = cap.map((c) => usableCapacity(c, bufferPct));
  const deficit = req.map((r, i) => Math.max(r - cap[i], 0));
  const left = req.map((r, i) => Math.max(usable[i] - r, 0));
  const sent = req.map(() => 0);
  const received = req.map(() => 0);
  const transfers: Transfer[] = [];
  const senders = rows
    .map((_, i) => i)
    .filter((i) => deficit[i] > 0)
    .sort((a, b) => rows[b].priority - rows[a].priority || compareText(rows[a].ward, rows[b].ward));
  for (const i of senders) {
    while (sent[i] < deficit[i] && left.some((l) => l > 0)) {
      const j = argmin(left.map((l, k) => (l > 0 ? (req[k] + received[k]) / cap[k] : Infinity)));
      const move = Math.min(deficit[i] - sent[i], left[j]);
      transfers.push({ city: rows[i].city, fromWard: rows[i].ward, toWard: rows[j].ward, patients: move });
      sent[i] += move;
      received[j] += move;
      left[j] -= move;
    }
  }
  const wards = rows.map((r, i) => ({
    ward: r.ward,
    city: r.city,
    required: req[i],
    capacity: cap[i],
    usable: usable[i],
    deficitBefore: deficit[i],
    sent: sent[i],
    received: received[i],
    unplaced: deficit[i] - sent[i],
    headroomAfter: left[i],
    utilizationAfter: (req[i] - sent[i] + received[i]) / cap[i],
  }));
  return [transfers, wards];
}

function citySummary(wards: RouteWard[], bufferPct: number): CitySummary {
  const sum = (pick: (w: RouteWard) => number) => wards.reduce((s, w) => s + pick(w), 0);
  const deficit = sum((w) => Math.max(w.required - w.capacity, 0));
  const headroom = sum((w) => Math.max(usableCapacity(w.capacity, bufferPct) - w.required, 0));
  const unplaced = sum((w) => w.unplaced);
  return {
    city: wards[0].city,
    required: sum((w) => w.required),
    capacity: sum((w) => w.capacity),
    usable: sum((w) => w.usable),
    utilizationPct: (sum((w) => w.required) / sum((w) => w.capacity)) * 100,
    moved: sum((w) => w.sent),
    maxFlow: Math.min(deficit, headroom),
    unplaced,
    headroomLeft: sum((w) => w.headroomAfter),
    alert: unplaced > 0 ? "CITY_SATURATED" : "OK",
  };
}

export function routeOverflow(table: RouteInput[], bufferPct: number): Routing {
  if (table.some((r) => r.capacity <= 0)) throw new Error("capacity must be > 0 for every ward");
  const cities = [...new Set(table.map((r) => r.city))].sort(compareText);
  const transfers: Transfer[] = [];
  const wards: RouteWard[] = [];
  const summaries: CitySummary[] = [];
  for (const city of cities) {
    const rows = table.filter((r) => r.city === city).sort((a, b) => compareText(a.ward, b.ward));
    const [cityTransfers, cityWards] = routeCity(rows, bufferPct);
    transfers.push(...cityTransfers);
    wards.push(...cityWards);
    summaries.push(citySummary(cityWards, bufferPct));
  }
  return { transfers, wards, cities: summaries };
}
