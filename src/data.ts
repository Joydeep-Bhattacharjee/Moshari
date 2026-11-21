export type Tier = "Low" | "Medium" | "High" | "Critical";
export type Language = "EN" | "বাংলা" | "EN + বাংলা";

export interface BackendForecastRecord {
  ward: string;
  week: string;
  horizon: number;
  pred: number;
  lo?: number;
  hi?: number;
  actual?: number | null;
  rain?: number | null;
  drivers?: number[];
}

// ==========================================
// 1. MOCK / STUB DATA (Replace or override when backend data is ready)
// ==========================================
export const MOCK_WARDS = [
  "Ward-01",
  "Ward-02",
  "Ward-04",
  "Ward-05",
  "Ward-07",
  "Ward-09",
  "Ward-12",
  "Ward-14",
  "Ward-16",
  "Ward-19",
  "Ward-21",
  "Ward-24",
] as const;

export const MOCK_WEEKS = Array.from({ length: 12 }, (_, i) =>
  new Date(Date.UTC(2025, 7, 25 - i * 7)).toISOString().slice(0, 10),
);

const MOCK_WARD_BASE_CASES = [
  0, 33, 23, 20, 46, 18, 30, 78, 42, 106, 22, 30, 118, 42, 63, 25, 17, 31, 60, 56, 20, 38, 30, 42,
  14,
];

export const DRIVER_NAMES = [
  ["Rain lags 2–4w", "২–৪ সপ্তাহ আগের বৃষ্টি"],
  ["Ward vulnerability", "ওয়ার্ডের ঝুঁকিপ্রবণতা"],
  ["Rainfall windows", "বৃষ্টিপাতের সময়কাল"],
  ["Humidity", "আর্দ্রতা"],
  ["Interactions", "পারস্পরিক প্রভাব"],
  ["Seasonality", "ঋতুগত প্রভাব"],
  ["Temperature", "তাপমাত্রা"],
] as const;

// ==========================================
// 2. DATA ADAPTER / OVERRIDE HOOK FOR PYTHON BACKEND OUTPUT
// ==========================================
let backendRecords: BackendForecastRecord[] | null = null;

/**
 * Call this helper once real JSON/CSV records from the Python backend are loaded.
 */
export function setBackendForecastData(records: BackendForecastRecord[] | null) {
  backendRecords = records;
}

function findBackendRecord(ward: string, week: string, horizon: number) {
  if (!backendRecords || backendRecords.length === 0) return undefined;
  return backendRecords.find(
    (r) => r.ward === ward && r.week === week && r.horizon === horizon,
  );
}

// Backward-compatible exports used by App.tsx and components
export const WARDS: string[] = [...MOCK_WARDS];
export const WEEKS: string[] = [...MOCK_WEEKS];

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
    mock: "Mock preview",
    notice: "A preview with purpose.",
    noticeBody:
      "You’re exploring realistic sample data. Live forecasts will appear when the model is connected.",
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
    demo: "Illustrative mock metrics — not measured model performance.",
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
    mock: "নমুনা প্রিভিউ",
    notice: "প্রস্তুতির জন্য একটি প্রিভিউ।",
    noticeBody: "এখানে বাস্তবসম্মত নমুনা তথ্য দেখানো হচ্ছে। মডেল সংযুক্ত হলে প্রকৃত পূর্বাভাস দেখা যাবে।",
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
    demo: "নমুনা পরিমাপ — প্রকৃত মডেলের কার্যকারিতা নয়।",
  },
};

// ==========================================
// 4. HELPERS, FORECAST ENGINE & VALIDATION
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

export function addWeeks(date: string, weeks: number) {
  return new Date(new Date(`${date}T00:00:00Z`).getTime() + weeks * 604800000)
    .toISOString()
    .slice(0, 10);
}

export function tierFor(cases: number): Tier {
  return cases >= 100 ? "Critical" : cases >= 50 ? "High" : cases >= 25 ? "Medium" : "Low";
}

function mockObservedCases(ward: string, target: string): number {
  const id = Number(ward.split("-")[1]);
  const index = Math.round((new Date(target).getTime() - new Date(WEEKS[0]).getTime()) / 604800000);
  const baseline = Math.max(
    2,
    Math.round((MOCK_WARD_BASE_CASES[id] ?? 40) * (1 + (index - 3) * 0.018)),
  );
  return Math.max(0, Math.round(baseline + Math.sin(index * 1.3 + id) * 11));
}

export function forecast(ward: string, week: string, horizon: number, multiplier = 1) {
  const target = addWeeks(week, horizon);
  const matched = findBackendRecord(ward, week, horizon);

  if (matched) {
    const pred = Math.max(
      0,
      Math.round(matched.pred * (1 + (multiplier - 1) * 0.42)),
    );
    const lo = matched.lo !== undefined ? Math.max(0, Math.round(matched.lo * (1 + (multiplier - 1) * 0.42))) : Math.max(0, Math.round(pred * 0.73));
    const hi = matched.hi !== undefined ? Math.round(matched.hi * (1 + (multiplier - 1) * 0.42)) : Math.round(pred * 1.24);
    const actual = matched.actual !== undefined ? matched.actual : target <= WEEKS[0] ? mockObservedCases(ward, target) : null;

    return {
      ward,
      pred,
      lo,
      hi,
      tier: tierFor(pred),
      target,
      actual,
    };
  }

  const id = Number(ward.split("-")[1]);
  const base = MOCK_WARD_BASE_CASES[id] ?? 40;
  const seasonal =
    1 + ((new Date(week).getTime() - new Date(WEEKS[0]).getTime()) / 604800000) * 0.018;
  const pred = Math.max(
    2,
    Math.round(base * seasonal * (1 + (horizon - 3) * 0.095) * (1 + (multiplier - 1) * 0.42)),
  );
  const lo = Math.max(0, Math.round(pred * 0.73));
  const hi = Math.round(pred * 1.24);

  return {
    ward,
    pred,
    lo,
    hi,
    tier: tierFor(pred),
    target,
    actual: target <= WEEKS[0] ? mockObservedCases(ward, target) : null,
  };
}

export function priority(week: string, horizon: number) {
  const order: Record<Tier, number> = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  return WARDS.map((ward) => forecast(ward, week, horizon)).sort(
    (a, b) => order[a.tier] - order[b.tier] || b.pred - a.pred,
  );
}

export function series(ward: string, week: string, horizon: number, multiplier: number) {
  const id = Number(ward.split("-")[1]);
  return Array.from({ length: 26 }, (_, i) => {
    const target = addWeeks(week, i - 25 + horizon);
    const dateIndex = Math.round(
      (new Date(target).getTime() - new Date(WEEKS[0]).getTime()) / 604800000,
    );
    const mockRain = Math.round(
      65 +
        43 * Math.sin(dateIndex * 0.32 + 1) +
        24 * Math.pow(Math.sin(dateIndex * 0.71 + id * 0.1), 2),
    );
    const origin = addWeeks(target, -horizon);
    const matched = findBackendRecord(ward, origin, horizon);
    const fit = forecast(ward, origin, horizon, multiplier);

    return {
      week: target,
      rain: target <= WEEKS[0] ? (matched?.rain ?? mockRain) : null,
      pred: fit.pred,
      actual: target <= WEEKS[0] ? (matched?.actual ?? mockObservedCases(ward, target)) : null,
      lo: fit.lo,
      hi: fit.hi,
    };
  });
}

export function driverValues(ward: string, horizon: number, multiplier: number) {
  const matched = findBackendRecord(ward, WEEKS[0], horizon);
  if (matched?.drivers && matched.drivers.length === DRIVER_NAMES.length) {
    return matched.drivers;
  }

  const id = Number(ward.split("-")[1]);
  return [
    22.4 * multiplier * (1 + (horizon - 3) * 0.1),
    14.8 + (id % 4) * 1.1,
    10.2 * multiplier,
    6.4,
    3.8,
    -3.2,
    -6.4,
  ];
}

/** One deterministic mock/backtest helper supplying the fit, folds, intervals and alerts. */
export function validationData(ward: string, horizon: number) {
  const history = series(ward, addWeeks("2025-06-30", -horizon), horizon, 1);
  const values = history.filter((p) => p.week >= "2025-02-03");
  const errors = values.map((p) => p.pred - p.actual!);
  const score = (items: number[]) => ({
    mae: items.reduce((s, n) => s + Math.abs(n), 0) / items.length,
    rmse: Math.sqrt(items.reduce((s, n) => s + n * n, 0) / items.length),
  });
  let tn = 0,
    fp = 0,
    fn = 0,
    tp = 0;
  values.forEach((p) => {
    if (p.actual! >= 50) {
      if (p.pred >= 50) tp++;
      else fn++;
    } else if (p.pred >= 50) fp++;
    else tn++;
  });
  const folds = Array.from({ length: 4 }, (_, i) =>
    score(
      errors.slice(Math.floor((i * errors.length) / 4), Math.floor(((i + 1) * errors.length) / 4)),
    ),
  );
  const baseline = (lag: number) =>
    score(
      values.map((p) => {
        const previous = history.find((row) => row.week === addWeeks(p.week, -lag));
        return (previous?.actual ?? history[0].actual!) - p.actual!;
      }),
    );
  return {
    values,
    folds,
    model: score(errors),
    lastWeek: baseline(1),
    seasonal: baseline(4),
    tn,
    fp,
    fn,
    tp,
    recall: tp / Math.max(1, tp + fn),
    precision: tp / Math.max(1, tp + fp),
    coverage: values.filter((p) => p.actual! >= p.lo && p.actual! <= p.hi).length / values.length,
  };
}