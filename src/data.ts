export type Tier = "Low" | "Medium" | "High" | "Critical";
export type Language = "EN" | "বাংলা" | "EN + বাংলা";

// ==========================================
// 1. DATA FILES WRITTEN BY `python -m src.export` (public/data/*.json)
// ==========================================
interface Band {
  pred: number[];
  lo: number[];
  hi: number[];
}

interface WardForecasts extends Band {
  actual: (number | null)[];
  drivers: number[][];
  scenario: Record<string, Band>;
}

export interface WardInfo {
  id: string;
  city: string;
  waterlogging: number;
  density: number;
  sanitation: number;
}

export interface ModelInfo {
  trained_at: string;
  train_start: string;
  train_end: string;
  holdout_start: string;
  holdout_end: string;
  sklearn_version: string;
}

export interface Dashboard {
  model: ModelInfo;
  thresholds: Record<string, number[]>;
  decision_scale: Record<string, number>;
  weeks: string[];
  first_selectable_week: string;
  multipliers: number[];
  driver_groups: string[];
  wards: WardInfo[];
  history: {
    weeks: string[];
    rain: Record<string, (number | null)[]>;
    cases: Record<string, (number | null)[]>;
  };
  forecasts: Record<string, Record<string, WardForecasts>>;
}

interface ErrorPair {
  mae: number;
  rmse: number;
}

interface HorizonValidation {
  model: string;
  per_fold: (ErrorPair & { fold: number })[];
  holdout: {
    model: ErrorPair;
    baselines: Record<string, ErrorPair>;
    beats_baselines: boolean;
    coverage_80: number;
    coverage_80_nonzero_weeks: number;
    alert_recall: number;
    alert_precision: number;
    tn: number;
    fp: number;
    fn: number;
    tp: number;
  };
  lag_gain_pct: number;
}

export interface ValidationFile {
  split: {
    data_start: string;
    data_end: string;
    holdout_train_end: string;
    holdout_start: string;
    folds: { fold: number; train_end: string; test_start: string; test_end: string }[];
  };
  lag_correlation: {
    lags: number[];
    spearman_raw: number[];
    spearman_deseasonalized: number[];
    peak_lag_deseasonalized: number;
  };
  horizons: Record<string, HorizonValidation>;
  test_series: Record<
    string,
    {
      dates: string[];
      wards: Record<string, Record<"y_true" | "pred" | "lo" | "hi", (number | null)[]>>;
    }
  >;
}

// Feature groups, in the order `python -m src.export` writes the driver values.
export const DRIVER_GROUPS = ["rain", "temperature", "humidity", "ward", "interactions", "season"] as const;

export const DRIVER_NAMES = [
  ["Recent rainfall", "সাম্প্রতিক বৃষ্টিপাত"],
  ["Temperature", "তাপমাত্রা"],
  ["Humidity", "আর্দ্রতা"],
  ["Ward vulnerability", "ওয়ার্ডের ঝুঁকিপ্রবণতা"],
  ["Interactions", "পারস্পরিক প্রভাব"],
  ["Seasonality", "ঋতুগত প্রভাব"],
] as const;

// Per group: [raises risk EN, lowers risk EN, raises risk BN, lowers risk BN].
const DRIVER_PHRASES: Record<(typeof DRIVER_GROUPS)[number], [string, string, string, string]> = {
  rain: [
    "heavy rain in recent weeks",
    "little recent rain",
    "সাম্প্রতিক সপ্তাহগুলোর ভারী বৃষ্টি",
    "সাম্প্রতিক কম বৃষ্টি",
  ],
  temperature: [
    "mosquito-friendly temperatures",
    "temperatures outside the mosquito range",
    "মশার অনুকূল তাপমাত্রা",
    "মশার প্রতিকূল তাপমাত্রা",
  ],
  humidity: ["high humidity", "low humidity", "উচ্চ আর্দ্রতা", "কম আর্দ্রতা"],
  ward: [
    "poor drainage, crowding or sanitation in this ward",
    "good drainage and sanitation in this ward",
    "এই ওয়ার্ডের দুর্বল নিষ্কাশন, ঘনবসতি বা স্যানিটেশন",
    "এই ওয়ার্ডের ভালো নিষ্কাশন ও স্যানিটেশন",
  ],
  interactions: [
    "recent rain falling on a vulnerable ward",
    "little rain on vulnerable areas",
    "ঝুঁকিপূর্ণ ওয়ার্ডে সাম্প্রতিক বৃষ্টি",
    "ঝুঁকিপূর্ণ এলাকায় কম বৃষ্টি",
  ],
  season: [
    "the time of year (monsoon season)",
    "the time of year (dry season)",
    "বছরের এই সময় (বর্ষাকাল)",
    "বছরের এই সময় (শুষ্ক মৌসুম)",
  ],
};

const CITY_NAMES: Record<string, [string, string, string]> = {
  "Dhaka North": ["Dhaka North City Corporation", "ঢাকা উত্তর", "ঢাকা উত্তর সিটি কর্পোরেশন"],
  "Dhaka South": ["Dhaka South City Corporation", "ঢাকা দক্ষিণ", "ঢাকা দক্ষিণ সিটি কর্পোরেশন"],
  Chattogram: ["Chattogram City Corporation", "চট্টগ্রাম", "চট্টগ্রাম সিটি কর্পোরেশন"],
  Gazipur: ["Gazipur City Corporation", "গাজীপুর", "গাজীপুর সিটি কর্পোরেশন"],
  Narayanganj: ["Narayanganj City Corporation", "নারায়ণগঞ্জ", "নারায়ণগঞ্জ সিটি কর্পোরেশন"],
};

const MIN_DRIVER_CASES = 0.05; // impacts smaller than this count as no effect (same as src/explain.py)

// ==========================================
// 2. LOADED DATA (filled once by initData before the app renders)
// ==========================================
let dashboard: Dashboard;
let validation: ValidationFile;
const weekIndex = new Map<string, number>();
const historyIndex = new Map<string, number>();
const wardIndex = new Map<string, WardInfo>();

export let WARDS: string[] = [];
export let WEEKS: string[] = []; // selectable forecast weeks, latest first
export let MULTIPLIERS: number[] = [];

export function initData(data: Dashboard, checks: ValidationFile) {
  if (data.driver_groups.join() !== DRIVER_GROUPS.join()) {
    throw new Error(`Unexpected driver groups in dashboard.json: ${data.driver_groups.join(", ")}`);
  }
  dashboard = data;
  validation = checks;
  weekIndex.clear();
  historyIndex.clear();
  wardIndex.clear();
  data.weeks.forEach((w, i) => weekIndex.set(w, i));
  data.history.weeks.forEach((w, i) => historyIndex.set(w, i));
  data.wards.forEach((w) => wardIndex.set(w.id, w));
  WARDS = data.wards.map((w) => w.id);
  WEEKS = data.weeks.filter((w) => w >= data.first_selectable_week).reverse();
  MULTIPLIERS = [...data.multipliers];
}

export function modelInfo(): ModelInfo {
  return dashboard.model;
}

export function wardInfo(ward: string): WardInfo {
  const info = wardIndex.get(ward);
  if (!info) throw new Error(`Unknown ward: ${ward}`);
  return info;
}

/** City of a ward: short name ("Dhaka North") and full city-corporation name. */
export function cityName(ward: string, mode: Language) {
  const city = wardInfo(ward).city;
  const [full, shortBn, fullBn] = CITY_NAMES[city] ?? [city, city, city];
  return { short: label_text(city, shortBn, mode), full: label_text(full, fullBn, mode) };
}

// ==========================================
// 3. UI CONSTANTS & BILINGUAL DICTIONARY
// ==========================================
export const TIER_COLORS: Record<Tier, { bg: string; border: string; text: string }> = {
  Low: { bg: "#E6F4F1", border: "#0072B2", text: "#083344" },
  Medium: { bg: "#FEF3C7", border: "#E69F00", text: "#451A03" },
  High: { bg: "#FFEDD5", border: "#D55E00", text: "#431407" },
  Critical: { bg: "#FDE2E4", border: "#800020", text: "#2B0608" },
};

export const TEXTS = {
  en: {
    forecast: "Forecast",
    priority: "Priority list",
    validation: "Validation",
    about: "About",
    title: "Small signals. Earlier action.",
    subtitle: "Ward-level intelligence to stay ahead of dengue outbreaks.",
    controls: "FORECAST CONTROLS",
    ward: "Select ward",
    week: "Forecast-origin week",
    horizon: "Forecast horizon",
    rainfall: "What-if rainfall",
    baseline: "Baseline",
    scenario: "Rainfall scenario",
    predicted: "Predicted cases",
    risk: "Outbreak risk",
    range: "80% prediction interval",
    actual: "Target week actual",
    pending: "Pending",
    timeline: "Weather meets outbreak risk",
    timelineSub: "26-week rainfall and dengue case trends",
    drivers: "What’s driving the risk?",
    driversSub: "Grouped feature contributions to this forecast",
    scenarioTitle: "A little more rain. A different outlook.",
    scenarioSub: "Explore how changing rainfall could shift the forecast.",
    context: "Your forecast at a glance",
    contextSub: "The context behind the numbers",
    mock: "Trained model",
    notice: "Real forecasts.",
    noticeBody:
      "Every number comes from the trained model. The latest week is dry season, so pick a monsoon week (Jun–Oct) to see alerts.",
    reset: "Reset to baseline",
    weeks: "weeks ahead",
    target: "Target week",
    observed: "Observed cases",
    rain: "Rainfall",
    predictedLine: "Predicted cases",
    band: "80% uncertainty",
    breeding: "2–4w breeding window",
    priorityTitle: "Put your teams where they matter.",
    prioritySub: "A ward-by-ward action list, ranked by outbreak risk.",
    download: "Download CSV",
    tableTitle: "Spray-team priority list",
    tableSub: "All wards · ranked by tier, then predicted cases",
    rank: "Rank",
    wardCol: "Ward",
    driver: "Top driver",
    heatmap: "The next three horizons",
    heatmapSub: "Outbreak risk by ward and forecast horizon",
    validationTitle: "Trust is built on evidence.",
    validationSub: "Transparent backtesting. Honest uncertainty. No shortcuts.",
    aboutTitle: "Earlier warning. Healthier neighborhoods.",
    aboutSub: "Meet Moshari, your ward-level early-warning companion.",
    demo: "Measured on the final holdout (Jul 2024 – Dec 2025), never used for training or model choice.",
  },
  bn: {
    forecast: "পূর্বাভাস",
    priority: "অগ্রাধিকার তালিকা",
    validation: "যাচাই",
    about: "পরিচিতি",
    title: "ক্ষুদ্র সংকেত। আগাম পদক্ষেপ।",
    subtitle: "ডেঙ্গুর প্রাদুর্ভাবের আগেই প্রস্তুতি নিতে ওয়ার্ডভিত্তিক তথ্য।",
    controls: "পূর্বাভাস নিয়ন্ত্রণ",
    ward: "ওয়ার্ড নির্বাচন",
    week: "পূর্বাভাসের সূচনা সপ্তাহ",
    horizon: "পূর্বাভাসের সময়সীমা",
    rainfall: "সম্ভাব্য বৃষ্টিপাত",
    baseline: "মূল পূর্বাভাস",
    scenario: "বৃষ্টিপাতের সম্ভাব্য দৃশ্য",
    predicted: "পূর্বাভাসিত কেস",
    risk: "প্রাদুর্ভাবের ঝুঁকি",
    range: "৮০% পূর্বাভাস সীমা",
    actual: "লক্ষ্য সপ্তাহের প্রকৃত কেস",
    pending: "অপেক্ষমাণ",
    timeline: "আবহাওয়া ও প্রাদুর্ভাবের ঝুঁকি",
    timelineSub: "২৬ সপ্তাহের বৃষ্টিপাত ও ডেঙ্গু কেসের প্রবণতা",
    drivers: "ঝুঁকির পেছনের কারণ কী?",
    driversSub: "এই পূর্বাভাসে বৈশিষ্ট্যগুলোর অবদান",
    scenarioTitle: "বৃষ্টি বাড়লে পূর্বাভাসও বদলায়।",
    scenarioSub: "বৃষ্টিপাতের পরিবর্তনে পূর্বাভাস কেমন হতে পারে দেখুন।",
    context: "এক নজরে আপনার পূর্বাভাস",
    contextSub: "সংখ্যার পেছনের প্রেক্ষাপট",
    mock: "প্রশিক্ষিত মডেল",
    notice: "প্রকৃত পূর্বাভাস।",
    noticeBody:
      "সব সংখ্যা প্রশিক্ষিত মডেল থেকে। সর্বশেষ সপ্তাহটি শুষ্ক মৌসুমের, তাই সতর্কতা দেখতে বর্ষার কোনো সপ্তাহ (জুন–অক্টোবর) বেছে নিন।",
    reset: "মূল অবস্থায় ফিরুন",
    weeks: "সপ্তাহ পরে",
    target: "লক্ষ্য সপ্তাহ",
    observed: "পর্যবেক্ষিত কেস",
    rain: "বৃষ্টিপাত",
    predictedLine: "পূর্বাভাসিত কেস",
    band: "৮০% অনিশ্চয়তা সীমা",
    breeding: "২–৪ সপ্তাহের প্রজননকাল",
    priorityTitle: "সঠিক জায়গায় আপনার দল পাঠান।",
    prioritySub: "ঝুঁকি অনুযায়ী সাজানো ওয়ার্ডভিত্তিক করণীয় তালিকা।",
    download: "CSV ডাউনলোড",
    tableTitle: "স্প্রে দলের অগ্রাধিকার তালিকা",
    tableSub: "সব ওয়ার্ড · ঝুঁকি ও কেস অনুযায়ী সাজানো",
    rank: "ক্রম",
    wardCol: "ওয়ার্ড",
    driver: "প্রধান কারণ",
    heatmap: "পরবর্তী তিন সময়সীমা",
    heatmapSub: "ওয়ার্ড ও সময়সীমাভিত্তিক প্রাদুর্ভাবের ঝুঁকি",
    validationTitle: "প্রমাণ থেকেই আস্থা।",
    validationSub: "স্বচ্ছ যাচাই ও অনিশ্চয়তার সৎ উপস্থাপন।",
    aboutTitle: "আগাম সতর্কতা। সুস্থ এলাকা।",
    aboutSub: "আপনার ওয়ার্ডভিত্তিক আগাম সতর্কতার সঙ্গী মশারি।",
    demo: "চূড়ান্ত যাচাই-পর্বে (জুলাই ২০২৪ – ডিসেম্বর ২০২৫) পরিমাপ করা; প্রশিক্ষণ বা মডেল বাছাইয়ে ব্যবহৃত হয়নি।",
  },
};

// ==========================================
// 4. HELPERS
// ==========================================
export function label_text(en: string, bn: string, mode: Language) {
  return mode === "বাংলা" ? bn : mode === "EN + বাংলা" ? `${en} / ${bn}` : en;
}

export function dateLabel(date: string, short = false) {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: short ? "short" : "long",
    ...(short ? {} : { year: "numeric" }),
    timeZone: "UTC",
  });
}

/** "4 Aug 2025": short label with the year, for week pickers. */
export function weekLabel(date: string) {
  return `${dateLabel(date, true)} ${date.slice(0, 4)}`;
}

export function addWeeks(date: string, weeks: number) {
  return new Date(new Date(`${date}T00:00:00Z`).getTime() + weeks * 604800000)
    .toISOString()
    .slice(0, 10);
}

// ==========================================
// 5. FORECASTS FROM THE EXPORTED MODEL OUTPUT
// ==========================================
const round1 = (n: number) => Math.round(n * 10) / 10;

function cuts(horizon: number, forPrediction: boolean) {
  const scale = forPrediction ? dashboard.decision_scale[String(horizon)] : 1;
  return dashboard.thresholds[String(horizon)].map((t) => t * scale);
}

function tierFromCuts(cases: number, edges: number[]): Tier {
  return cases >= edges[2] ? "Critical" : cases >= edges[1] ? "High" : cases >= edges[0] ? "Medium" : "Low";
}

/** Tier of a forecast: training thresholds lowered by the decision scale tuned for alert recall. */
export function tierFor(cases: number, horizon: number): Tier {
  return tierFromCuts(cases, cuts(horizon, true));
}

/** Tier of observed cases, using the training thresholds themselves. */
export function actualTierFor(cases: number, horizon: number): Tier {
  return tierFromCuts(cases, cuts(horizon, false));
}

/** Nearest precomputed rain multiplier (0.5x to 2x in 0.25 steps). */
export function snapMultiplier(multiplier: number) {
  return MULTIPLIERS.reduce((best, m) =>
    Math.abs(m - multiplier) < Math.abs(best - multiplier) ? m : best,
  );
}

function wardForecasts(ward: string, horizon: number) {
  const block = dashboard.forecasts[String(horizon)]?.[ward];
  if (!block) throw new Error(`No forecasts for ${ward} at ${horizon} weeks`);
  return block;
}

function indexOf(week: string) {
  const i = weekIndex.get(week);
  if (i === undefined) throw new Error(`No forecast for the week of ${week}`);
  return i;
}

export function hasForecast(week: string) {
  return weekIndex.has(week);
}

export function forecast(ward: string, week: string, horizon: number, multiplier = 1) {
  const block = wardForecasts(ward, horizon);
  const i = indexOf(week);
  const m = snapMultiplier(multiplier);
  const band: Band = m === 1 ? block : block.scenario[String(m)];
  const pred = round1(band.pred[i]);
  return {
    ward,
    pred,
    lo: round1(band.lo[i]),
    hi: round1(band.hi[i]),
    tier: tierFor(pred, horizon),
    target: addWeeks(week, horizon),
    actual: block.actual[i],
  };
}

export function priority(week: string, horizon: number) {
  const order: Record<Tier, number> = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  return WARDS.map((ward) => forecast(ward, week, horizon)).sort(
    (a, b) => order[a.tier] - order[b.tier] || b.pred - a.pred,
  );
}

function observed(ward: string, week: string, key: "rain" | "cases") {
  const i = historyIndex.get(week);
  return i === undefined ? null : dashboard.history[key][ward][i];
}

/** 26 target weeks ending at this forecast's target: rain, what happened, and what was forecast. */
export function series(ward: string, week: string, horizon: number, multiplier: number) {
  const block = wardForecasts(ward, horizon);
  return Array.from({ length: 26 }, (_, k) => {
    const origin = addWeeks(week, k - 25);
    const target = addWeeks(origin, horizon);
    const i = weekIndex.get(origin);
    const fit =
      origin === week
        ? forecast(ward, week, horizon, multiplier)
        : i === undefined
          ? null
          : { pred: round1(block.pred[i]), lo: round1(block.lo[i]), hi: round1(block.hi[i]) };
    return {
      week: target,
      rain: observed(ward, target, "rain"),
      actual: observed(ward, target, "cases"),
      pred: fit?.pred ?? null,
      lo: fit?.lo ?? null,
      hi: fit?.hi ?? null,
    };
  });
}

/** Signed change in predicted cases from each feature group (order of DRIVER_NAMES). */
export function driverValues(ward: string, week: string, horizon: number) {
  return wardForecasts(ward, horizon).drivers[indexOf(week)];
}

/** Index into DRIVER_NAMES of the factor that raises risk most, or -1 when none does. */
export function topDriverIndex(ward: string, week: string, horizon: number) {
  const values = driverValues(ward, week, horizon);
  const best = values.reduce((bi, v, i) => (v > values[bi] ? i : bi), 0);
  return values[best] > MIN_DRIVER_CASES ? best : -1;
}

export function topDriverLabel(ward: string, week: string, horizon: number, mode: Language) {
  const i = topDriverIndex(ward, week, horizon);
  return i < 0
    ? label_text("None", "নেই", mode)
    : label_text(DRIVER_NAMES[i][0], DRIVER_NAMES[i][1], mode);
}

/** Plain-language reason, mirroring driver_sentence in src/explain.py. */
export function driverSentence(ward: string, week: string, horizon: number, mode: Language) {
  const values = driverValues(ward, week, horizon);
  const tier = forecast(ward, week, horizon).tier;
  const ranked = DRIVER_GROUPS.map((g, i) => ({ g, v: values[i] }));
  const raising = ranked
    .filter((d) => d.v > MIN_DRIVER_CASES)
    .sort((a, b) => b.v - a.v)
    .slice(0, 2);
  if (raising.length > 0) {
    const en = raising.map((d) => DRIVER_PHRASES[d.g][0]).join(" and ");
    const bn = raising.map((d) => DRIVER_PHRASES[d.g][2]).join(" ও ");
    return label_text(
      `${tier} risk in ${horizon} weeks, mainly driven by ${en}.`,
      `${horizon} সপ্তাহ পর ${tier} ঝুঁকি, মূলত ${bn}-এর কারণে।`,
      mode,
    );
  }
  const lowering = [...ranked].sort((a, b) => a.v - b.v).slice(0, 2);
  const en = lowering.map((d) => DRIVER_PHRASES[d.g][1]).join(" and ");
  const bn = lowering.map((d) => DRIVER_PHRASES[d.g][3]).join(" ও ");
  return label_text(
    `${tier} risk in ${horizon} weeks, kept down by ${en}.`,
    `${horizon} সপ্তাহ পর ${tier} ঝুঁকি; ${bn} ঝুঁকি কমিয়ে রাখছে।`,
    mode,
  );
}

// ==========================================
// 6. VALIDATION (measured by src/selection.py and src/train.py)
// ==========================================
export function validationData(ward: string, horizon: number) {
  const h = validation.horizons[String(horizon)];
  const holdout = h.holdout;
  const ts = validation.test_series[String(horizon)];
  const wardSeries = ts.wards[ward];
  const values = ts.dates
    .map((week, i) => ({
      week,
      pred: wardSeries.pred[i],
      lo: wardSeries.lo[i],
      hi: wardSeries.hi[i],
      actual: wardSeries.y_true[i],
    }))
    .filter(
      (p): p is { week: string; pred: number; lo: number; hi: number; actual: number } =>
        p.actual !== null && p.pred !== null && p.lo !== null && p.hi !== null,
    );
  const wardMae =
    values.reduce((s, p) => s + Math.abs(p.pred - p.actual), 0) / Math.max(1, values.length);
  return {
    values,
    folds: h.per_fold,
    model: holdout.model,
    wardMae,
    wardMean: holdout.baselines["B1_ward_mean"],
    seasonal: holdout.baselines["B2_seasonal_naive"],
    beatsBaselines: holdout.beats_baselines,
    tn: holdout.tn,
    fp: holdout.fp,
    fn: holdout.fn,
    tp: holdout.tp,
    recall: holdout.alert_recall,
    precision: holdout.alert_precision,
    coverage: holdout.coverage_80,
    coverageNonzero: holdout.coverage_80_nonzero_weeks,
    lagGainPct: h.lag_gain_pct,
    modelName: h.model,
    split: validation.split,
    lag: validation.lag_correlation,
  };
}
