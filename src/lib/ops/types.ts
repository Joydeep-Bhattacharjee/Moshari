// Types for the Phase 2 decision core in the browser. The data comes from
// `python -m src.ops.ui_export` (public/data/ops/config.json and forecasts.json).

export type Confidence = "likely" | "bad";
export type CrewMode = "priority" | "roi";
export type Band = "low" | "base" | "high";
export type Alert = "OK" | "WARNING" | "CRITICAL";

export const SALINE = "saline_bags_needed";
export const KITS = "diagnostic_kits_needed";
export const BEDS = "hospital_beds_required";
export type Resource = typeof SALINE | typeof KITS;

export interface Scenario {
  asof: string;
  weeks: number;
  stock_pct: number;
  floor_pct: number;
  confidence: Confidence;
  crews_total: number;
  crew_mode: CrewMode;
  band: Band;
  apply_intervention: boolean;
}

export interface WardConfig {
  id: string;
  city: string;
  density: number;
  waterlog: number;
  sanitation: number;
  capacity: number;
}

export interface DrainageCoef {
  waterlog: number;
  rain_x_waterlog: number;
}

export interface OpsConstants {
  tiers: string[];
  thresholds: Record<string, number[]>;
  decision_scale: Record<string, number>;
  window_plan: Record<string, [number, number]>;
  max_window_weeks: number;
  supply_per_1000: Record<string, number>;
  confidence_cols: Record<Confidence, string>;
  risk_norm: number[];
  weights: { risk: number; density: number; cases: number };
  stock_pct_range: [number, number];
  critical_fill: number;
  high_risk_fill: number;
  high_risk_from: number;
  crews_by_tier: number[];
  poor_drainage_from: number;
  buffer_pct: number;
  bands: Record<Band, number>;
  crew_saturation: number;
  max_crews_per_ward: number;
  ramp_by_week: Record<string, number>;
  waterlog_floor: number;
  effect_horizon_by_week: Record<string, number>;
  defaults: Scenario;
}

export interface OpsConfig {
  provenance: {
    data_hash: string;
    git_commit: string;
    model_trained_at: string;
    train_end: string;
    capacity_source: string;
  };
  constants: OpsConstants;
  drainage: Record<string, DrainageCoef>;
  driver_labels: string[];
  wards: WardConfig[];
}

export interface WardWindow {
  expected: number[];
  p10: number[];
  p90: number[];
  tier_rank: number[];
  actual: (number | null)[];
  top_driver: number[];
  rain_sum: number;
}

export interface OpsForecasts {
  asof_weeks: string[];
  driver_labels: string[];
  windows: Record<string, Record<string, WardWindow>>;
}

/** One ward-week of a forecast window (src/ops/forecast_window.py WINDOW_COLS). */
export interface WindowRow {
  ward: string;
  city: string;
  weekAhead: number;
  targetWeek: string;
  modelHorizon: number;
  expected: number;
  p10: number;
  p90: number;
  tierRank: number;
  actual: number | null;
  topDriver: string;
}

export interface SimRow extends WindowRow {
  crews: number;
  reduction: number;
  waterlog: number;
  waterlogAfter: number;
  effectRatio: number;
  expectedAfter: number;
  p90After: number;
  prevented: number;
}

export interface DemandRow {
  ward: string;
  city: string;
  windowWeeks: number;
  cases: number;
  peakWeeklyCases: number;
  saline: number;
  kits: number;
  beds: number;
  riskRank: number;
  density: number;
  waterlog: number;
}

export interface AllocationRow {
  ward: string;
  city: string;
  resource: Resource;
  priority: number;
  priorityRank: number;
  riskRank: number;
  need: number;
  floor: number;
  allocated: number;
  fill: number;
  deficit: number;
  alert: Alert;
}

export interface Transfer {
  city: string;
  fromWard: string;
  toWard: string;
  patients: number;
}

export interface RouteWard {
  ward: string;
  city: string;
  required: number;
  capacity: number;
  usable: number;
  deficitBefore: number;
  sent: number;
  received: number;
  unplaced: number;
  headroomAfter: number;
  utilizationAfter: number;
}

export interface CitySummary {
  city: string;
  required: number;
  capacity: number;
  usable: number;
  utilizationPct: number;
  moved: number;
  maxFlow: number;
  unplaced: number;
  headroomLeft: number;
  alert: "OK" | "CITY_SATURATED";
}

export interface Routing {
  transfers: Transfer[];
  wards: RouteWard[];
  cities: CitySummary[];
}
