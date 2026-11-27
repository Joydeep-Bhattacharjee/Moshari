// Spray-crew need and priority-order assignment (mirror of src/ops/crews.py).
import { greedyFill } from "./allocate.ts";
import type { OpsConstants } from "./types.ts";

/** Tier crews (Low 0, Medium 1, High 2, Critical 3) + 1 if water-logging >= 0.75. */
export function crewsNeeded(riskRank: number, waterlog: number, c: OpsConstants): number {
  return c.crews_by_tier[riskRank] + (waterlog >= c.poor_drainage_from ? 1 : 0);
}

/** Each ward, in priority order, gets up to its need until the crews run out. */
export function assignCrews(needInPriorityOrder: number[], totalCrews: number): number[] {
  if (totalCrews < 0) throw new Error(`total crews must be >= 0, got ${totalCrews}`);
  return greedyFill(needInPriorityOrder, Math.floor(totalCrews));
}
