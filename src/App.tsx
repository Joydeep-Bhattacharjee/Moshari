import Validation from "./components/Validation";
import About from "./components/About";
import { Component, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleHelp,
  Clock3,
  CloudRain,
  FlaskConical,
  Focus,
  Globe2,
  Info,
  Layers3,
  MapPin,
  Radar,
  RotateCcw,
  Settings2,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Waves,
  X,
} from "lucide-react";
import type { Data, Layout } from "plotly.js";
import Chart from "./components/Chart";
import { Badge, CardHeader } from "./components/DashboardUI";
import {
  addWeeks,
  cityName,
  dateLabel,
  driverSentence,
  driverValues,
  DRIVER_NAMES,
  forecast,
  hasForecast,
  label_text,
  priority,
  series,
  TEXTS,
  TIER_COLORS,
  topDriverLabel,
  WARDS,
  wardInfo,
  WEEKS,
  weekLabel,
  type Language,
  type Tier,
} from "./data";

type TextKey = keyof typeof TEXTS.en;
type Tab = "forecast" | "priority" | "validation" | "about";

class Guard extends Component<{ children: ReactNode; fallback: string }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="error-notice">
        <CircleAlert size={18} />
        {this.props.fallback}
      </div>
    ) : (
      this.props.children
    );
  }
}

function Timeline({
  ward,
  week,
  horizon,
  multiplier,
  t,
  l,
}: {
  ward: string;
  week: string;
  horizon: number;
  multiplier: number;
  t: (k: TextKey) => string;
  l: (en: string, bn: string) => string;
}) {
  const points = series(ward, week, horizon, multiplier);
  const x = points.map((p) => p.week);
  const data: Data[] = [
    {
      x,
      y: points.map((p) => p.rain),
      type: "bar",
      name: t("rain"),
      marker: { color: "#56B4E9" },
      width: 604800000 * 0.58,
      yaxis: "y2",
      hovertemplate: "%{x|%d %b}<br>%{y} mm<extra></extra>",
    },
    {
      x,
      y: points.map((p) => p.lo),
      type: "scatter",
      mode: "lines",
      line: { width: 0 },
      hoverinfo: "skip",
      name: "Lower interval",
    },
    {
      x,
      y: points.map((p) => p.hi),
      type: "scatter",
      mode: "lines",
      fill: "tonexty",
      fillcolor: "rgba(59, 130, 246, 0.16)",
      line: { width: 0 },
      hoverinfo: "skip",
      name: t("band"),
    },
    {
      x,
      y: points.map((p) => p.actual),
      type: "scatter",
      mode: "lines",
      name: t("observed"),
      line: { color: "#1E293B", width: 2.6, shape: "spline" },
      hovertemplate: `%{y} ${l("cases", "কেস")}<extra>${t("observed")}</extra>`,
    },
    {
      x,
      y: points.map((p) => p.pred),
      type: "scatter",
      mode: "lines",
      name: t("predictedLine"),
      line: { color: "#258b82", width: 2.3, dash: "dot", shape: "spline" },
      hovertemplate: `%{y} ${l("cases", "কেস")}<extra>${t("predicted")}</extra>`,
    },
  ];
  const layout: Partial<Layout> = {
    margin: { l: 33, r: 32, t: 27, b: 31 },
    barmode: "overlay",
    hovermode: "x unified",
    xaxis: {
      showgrid: false,
      zeroline: false,
      tickformat: "%d %b",
      nticks: 7,
      fixedrange: true,
      tickfont: { size: 9 },
    },
    yaxis: {
      title: { text: l("Cases", "কেস"), font: { size: 9 }, standoff: 5 },
      gridcolor: "#edf1f5",
      zeroline: false,
      range: [0, Math.max(1, ...points.map((p) => Math.max(p.hi ?? 0, p.actual ?? 0))) * 1.3],
      fixedrange: true,
    },
    yaxis2: {
      title: { text: "mm", font: { size: 9 } },
      overlaying: "y",
      side: "right",
      range: [0, Math.max(50, ...points.map((p) => p.rain ?? 0)) * 1.15],
      showgrid: false,
      zeroline: false,
      fixedrange: true,
      nticks: 5,
    },
    shapes: [
      {
        type: "rect",
        x0: addWeeks(week, -4),
        x1: addWeeks(week, -2),
        y0: 0,
        y1: 1,
        yref: "paper",
        fillcolor: "rgba(230, 159, 0, 0.14)",
        line: { width: 0 },
        layer: "below",
      },
      {
        type: "line",
        x0: week,
        x1: week,
        y0: 0,
        y1: 1,
        yref: "paper",
        line: { color: "#94a3b8", width: 1, dash: "dot" },
      },
    ],
    annotations: [
      {
        x: addWeeks(week, -3),
        y: 1.07,
        yref: "paper",
        text: t("breeding"),
        showarrow: false,
        font: { size: 8, color: "#a16d13" },
      },
    ],
  };
  return (
    <section className="card timeline-card">
      <CardHeader
        title={t("timeline")}
        subtitle={t("timelineSub")}
        action={<span className="subtle-pill">26 {l("weeks", "সপ্তাহ")}</span>}
      />
      <div className="chart-legend">
        <span>
          <i className="legend-bar" />
          {t("rain")}
        </span>
        <span>
          <i className="legend-line" />
          {t("observed")}
        </span>
        <span>
          <i className="legend-dash" />
          {t("predictedLine")}
        </span>
        <span>
          <i className="legend-band" />
          {t("band")}
        </span>
      </div>
      <Chart data={data} layout={layout} height={239} label={t("timeline")} />
      <div className="chart-footnote">
        <Info size={12} />
        <span>
          {l(
            "Rainfall today can influence dengue risk 2–4 weeks later.",
            "আজকের বৃষ্টিপাত ২–৪ সপ্তাহ পর ডেঙ্গুর ঝুঁকিতে প্রভাব ফেলতে পারে।",
          )}
        </span>
      </div>
    </section>
  );
}

export default function App() {
  const [lang, setLang] = useState<Language>("EN");
  const [ward, setWard] = useState(WARDS.includes("DSCC_Ward_05") ? "DSCC_Ward_05" : WARDS[0]);
  const [week, setWeek] = useState(WEEKS[0]);
  const [horizon, setHorizon] = useState(3);
  const [multiplier, setMultiplier] = useState(1);
  const [tab, setTab] = useState<Tab>("forecast");
  const [notice, setNotice] = useState(true);
  const t = (key: TextKey) => label_text(TEXTS.en[key], TEXTS.bn[key], lang);
  const l = (en: string, bn: string) => label_text(en, bn, lang);
  const current = forecast(ward, week, horizon, multiplier);
  const baseline = forecast(ward, week, horizon);
  const ranked = useMemo(() => priority(week, horizon), [week, horizon]);
  const drivers = driverValues(ward, week, horizon);
  const change = Math.round((current.pred - baseline.pred) * 10) / 10;
  const info = wardInfo(ward);
  const city = cityName(ward, lang);
  const previousWeek = addWeeks(week, -1);
  const signed = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(1)}`;
  const times = (m: number) => (Number.isInteger(m) ? m.toFixed(1) : String(m));
  const level = (v: number) =>
    v >= 0.66 ? l("High", "উচ্চ") : v >= 0.45 ? l("Moderate", "মাঝারি") : l("Low", "কম");
  const advice = (tier: Tier) =>
    tier === "Critical"
      ? l("Immediate attention", "তাৎক্ষণিক নজর দিন")
      : tier === "High"
        ? l("Prioritize intervention", "হস্তক্ষেপে অগ্রাধিকার")
        : tier === "Medium"
          ? l("Increase surveillance", "নজরদারি বাড়ান")
          : l("Continue monitoring", "পর্যবেক্ষণ অব্যাহত রাখুন");
  const tabs: { id: Tab; icon: typeof Activity }[] = [
    { id: "forecast", icon: Activity },
    { id: "priority", icon: Layers3 },
    { id: "validation", icon: ShieldCheck },
    { id: "about", icon: CircleHelp },
  ];
  function downloadCsv() {
    const rows = [
      ["Rank", "Ward", "City", "Risk Tier", "Predicted Cases", "Low (80%)", "High (80%)", "Top Driver"],
      ...ranked.map((r, i) => [
        i + 1,
        r.ward,
        wardInfo(r.ward).city,
        r.tier,
        r.pred,
        r.lo,
        r.hi,
        topDriverLabel(r.ward, week, horizon, "EN"),
      ]),
    ];
    const url = URL.createObjectURL(
      new Blob(["\uFEFF" + rows.map((row) => row.join(",")).join("\n")], {
        type: "text/csv;charset=utf-8;",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `moshari-priority-${week}-${horizon}w.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className={`app-shell ${lang === "EN + বাংলা" ? "bilingual" : ""}`}>
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setTab("forecast");
          }}
          aria-label="Moshari home"
        >
          <span className="brand-mark">
            <Radar size={25} strokeWidth={1.6} />
          </span>
          <span>
            Moshari<span className="brand-light"></span>
            <small>ANTICIPATE. ACT. PROTECT.</small>
          </span>
        </a>
        <div className="workspace-label">
          <span className="workspace-icon">
            <MapPin size={15} />
          </span>
          <div>
            {l("Bangladesh · 5 city corporations", "বাংলাদেশ · ৫টি সিটি কর্পোরেশন")}
            <small>{l("Ward surveillance workspace", "ওয়ার্ড নজরদারি কর্মক্ষেত্র")}</small>
          </div>
          <span className="online-dot" />
        </div>
        <div className="sidebar-controls">
          <div className="section-eyebrow">
            {t("controls")}
            <Settings2 size={13} />
          </div>
          <label className="control-label" htmlFor="ward">
            <MapPin size={14} />
            {t("ward")}
          </label>
          <div className="select-wrap">
            <select id="ward" value={ward} onChange={(e) => setWard(e.target.value)}>
              {WARDS.map((w) => (
                <option key={w} value={w}>
                  {w} · {cityName(w, lang).short}
                </option>
              ))}
            </select>
            <ChevronDown size={14} />
          </div>
          <div className="field-note">
            <span className="teal-dot" />
            {city.full}
          </div>
          <label className="control-label" htmlFor="week">
            <CalendarDays size={14} />
            {t("week")}
          </label>
          <div className="select-wrap">
            <select id="week" value={week} onChange={(e) => setWeek(e.target.value)}>
              {WEEKS.map((w) => (
                <option value={w} key={w}>
                  {weekLabel(w)}{w === WEEKS[0] ? ` · ${l("Latest", "সর্বশেষ")}` : ""}
                </option>
              ))}
            </select>
            <ChevronDown size={14} />
          </div>
          <label className="control-label">
            <Clock3 size={14} />
            {t("horizon")}
          </label>
          <div className="horizon-switch" role="group" aria-label={t("horizon")}>
            {[2, 3, 4].map((h) => (
              <button
                key={h}
                className={horizon === h ? "selected" : ""}
                onClick={() => setHorizon(h)}
              >
                {h} {l("weeks", "সপ্তাহ")}
                {horizon === h && <span />}
              </button>
            ))}
          </div>
          <p className="target-note">
            {t("target")}: <strong>{dateLabel(current.target, true)}</strong>
          </p>
          <div className="sidebar-divider" />
          <label className="control-label rain-label" htmlFor="rain">
            <CloudRain size={15} />
            {t("rainfall")}
            <span className="experimental-label">{l("EXPLORE", "দেখুন")}</span>
          </label>
          <p className="slider-description">
            {l("What changes if it rains more?", "বৃষ্টি বাড়লে কী বদলায়?")}
          </p>
          <div className="rain-multiplier">
            {times(multiplier)}
            <span>×</span>
            <small>{l("normal rainfall", "স্বাভাবিক বৃষ্টিপাত")}</small>
          </div>
          <input
            id="rain"
            aria-label={t("rainfall")}
            type="range"
            min=".5"
            max="2"
            step=".25"
            value={multiplier}
            onChange={(e) => setMultiplier(Number(e.target.value))}
            style={{ "--range": `${((multiplier - 0.5) / 1.5) * 100}%` } as CSSProperties}
          />
          <div className="range-labels">
            <span>0.5×</span>
            <span>1.0×</span>
            <span>2.0×</span>
          </div>
          <button
            className="reset-button"
            onClick={() => setMultiplier(1)}
            disabled={multiplier === 1}
          >
            <RotateCcw size={12} />
            {t("reset")}
          </button>
          <div className="control-info">
            <Info size={14} />
            <p>
              {l(
                "A planning tool, not a certainty. Use forecasts alongside local surveillance.",
                "পরিকল্পনার সহায়ক, নিশ্চয়তা নয়। স্থানীয় নজরদারির সঙ্গে পূর্বাভাস ব্যবহার করুন।",
              )}
            </p>
          </div>
        </div>
        <div className="sidebar-bottom">
          <div className="system-title">
            <span className="online-dot" />
            {l("All systems ready", "সিস্টেম প্রস্তুত")}
            <ShieldCheck size={14} />
          </div>
          <p>{l("Local intelligence. Zero API costs.", "স্থানীয় তথ্য। কোনো API খরচ নেই।")}</p>
          <div className="sidebar-version">
            <span>
              Moshari <b>v2.0</b>
            </span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <span>{l("Surveillance", "নজরদারি")}</span>
            <ChevronRight size={13} />
            <strong>{t(tab)}</strong>
          </div>
          <div className="topbar-right">
            <span className="mock-status">
              <span />
              {t("mock")}
            </span>
            <div className="topbar-separator" />
            <Globe2 size={15} className="globe-icon" />
            <div className="language-switch" aria-label="Language">
              {(["EN", "বাংলা", "EN + বাংলা"] as Language[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setLang(v)}
                  className={lang === v ? "active" : ""}
                  aria-pressed={lang === v}
                >
                  {v}
                </button>
              ))}
            </div>
            <span className="user-avatar" title={l("Public health workspace", "জনস্বাস্থ্য কর্মক্ষেত্র")}>
              MS
            </span>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span />
                {l("DENGUE EARLY-WARNING SYSTEM", "ডেঙ্গু আগাম সতর্কতা ব্যবস্থা")}
              </div>
              <h1>
                {t(
                  tab === "forecast"
                    ? "title"
                    : tab === "priority"
                      ? "priorityTitle"
                      : tab === "validation"
                        ? "validationTitle"
                        : "aboutTitle",
                )}
              </h1>
              <p>
                {t(
                  tab === "forecast"
                    ? "subtitle"
                    : tab === "priority"
                      ? "prioritySub"
                      : tab === "validation"
                        ? "validationSub"
                        : "aboutSub",
                )}
              </p>
            </div>
            <div className="report-date">
              <CalendarDays size={16} />
              <div>
                <span>{l("FORECAST ORIGIN", "পূর্বাভাসের সূচনা")}</span>
                <strong>{weekLabel(week)}</strong>
              </div>
            </div>
          </div>
          <nav className="tabs" aria-label={l("Dashboard sections", "ড্যাশবোর্ডের বিভাগ")}>
            {tabs.map(({ id, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={tab === id ? "active" : ""}
                aria-current={tab === id ? "page" : undefined}
              >
                <Icon size={16} />
                {t(id)}
                {id === "priority" && <span className="tab-count">{WARDS.length}</span>}
              </button>
            ))}
            <span className="tabs-right">
              <span className="teal-dot" />
              {ward}
              <span className="tiny-divider">/</span>
              {horizon}
              {l("w outlook", " সপ্তাহের পূর্বাভাস")}
            </span>
          </nav>
          {notice && (
            <div className="preview-notice">
              <span className="notice-icon">
                <FlaskConical size={17} />
              </span>
              <p>
                <strong>{t("notice")}</strong> {t("noticeBody")}
              </p>
              <button
                onClick={() => setNotice(false)}
                aria-label={l("Dismiss preview notice", "প্রিভিউ বার্তা বন্ধ করুন")}
              >
                <X size={15} />
              </button>
            </div>
          )}
          <Guard
            key={tab}
            fallback={l(
              "This view could not be displayed. Try another ward or week, or refresh the page.",
              "এই অংশটি দেখানো যাচ্ছে না। অন্য ওয়ার্ড বা সপ্তাহ বেছে নিন অথবা পেজ রিফ্রেশ করুন।",
            )}
          >
            {tab === "forecast" && (
              <>
                <div className="section-topline">
                  <div>
                    <h2>
                      {ward} <span>{l("forecast overview", "পূর্বাভাসের সারসংক্ষেপ")}</span>
                    </h2>
                    <span className="location-caption">
                      <MapPin size={11} />
                      {city.short}
                    </span>
                  </div>
                  <span className="horizon-caption">
                    {horizon}-{l("week outlook", "সপ্তাহের পূর্বাভাস")}
                    <span>·</span>
                    {t("target")}: <strong>{dateLabel(current.target, true)}</strong>
                  </span>
                </div>
                <div className="kpi-grid">
                  <section className="card kpi risk-kpi">
                    <div className="kpi-label">
                      {t("risk")}
                      <span className="metric-icon orange">
                        <ShieldCheck size={16} />
                      </span>
                    </div>
                    <div className="risk-kpi-value">
                      <Badge tier={current.tier} />
                      <span className="risk-scale">
                        <i />
                        <i />
                        <i
                          className={
                            current.tier === "High" || current.tier === "Critical" ? "filled" : ""
                          }
                        />
                        <i className={current.tier === "Critical" ? "critical-filled" : ""} />
                      </span>
                    </div>
                    <p>
                      <span className="small-orange-dot" />
                      {advice(current.tier)}
                    </p>
                  </section>
                  <section className="card kpi">
                    <div className="kpi-label">
                      {t("predicted")}
                      <span className="metric-icon teal">
                        <TrendingUp size={16} />
                      </span>
                    </div>
                    <div className="kpi-value">
                      {current.pred}
                      <span>{l("cases", "কেস")}</span>
                    </div>
                    <p>
                      <span className="trend">
                        <ArrowUpRight size={12} />
                        {hasForecast(previousWeek)
                          ? signed(current.pred - forecast(ward, previousWeek, horizon).pred)
                          : "—"}
                      </span>
                      {l("vs. previous week", "আগের সপ্তাহের তুলনায়")}
                    </p>
                  </section>
                  <section className="card kpi">
                    <div className="kpi-label">
                      {t("range")}
                      <span className="metric-icon blue">
                        <Focus size={16} />
                      </span>
                    </div>
                    <div className="kpi-value interval">
                      {current.lo}
                      <span className="range-dash">–</span>
                      {current.hi}
                    </div>
                    <p>{l("Expected range of reported cases", "রিপোর্ট করা কেসের সম্ভাব্য সীমা")}</p>
                  </section>
                  <section className="card kpi">
                    <div className="kpi-label">
                      {t("actual")}
                      <span className="metric-icon gray">
                        <CalendarDays size={16} />
                      </span>
                    </div>
                    <div className={`kpi-value ${current.actual === null ? "pending-value" : ""}`}>
                      {current.actual === null ? (
                        <>
                          <Clock3 size={23} strokeWidth={1.5} />
                          {t("pending")}
                        </>
                      ) : (
                        current.actual
                      )}
                    </div>
                    <p>
                      {current.actual === null
                        ? l("Awaiting target-week observations", "লক্ষ্য সপ্তাহের তথ্যের অপেক্ষায়")
                        : l("Reported target-week observations", "লক্ষ্য সপ্তাহের রিপোর্ট করা তথ্য")}
                    </p>
                  </section>
                </div>
                <div className="charts-grid">
                  <Timeline
                    ward={ward}
                    week={week}
                    horizon={horizon}
                    multiplier={multiplier}
                    t={t}
                    l={l}
                  />
                  <section className="card driver-card">
                    <CardHeader
                      title={t("drivers")}
                      subtitle={t("driversSub")}
                      action={
                        <span
                          className="help-icon"
                          title={l(
                            "Change in predicted cases when each group is set to its typical (training median) value. Not a causal effect.",
                            "প্রতিটি গ্রুপকে সাধারণ (প্রশিক্ষণ-মধ্যমা) মানে রাখলে পূর্বাভাস কতটা বদলায়; এটি কারণ-ফল নয়।",
                          )}
                        >
                          <Info size={15} />
                        </span>
                      }
                    />
                    <div className="drivers-chart">
                      {DRIVER_NAMES.map(([en, bn], i) => (
                        <div className="driver-row" key={en}>
                          <span>{l(en, bn)}</span>
                          <div className="driver-track">
                            <div
                              className={`driver-bar ${drivers[i] < 0 ? "negative" : ""}`}
                              style={{
                                width: `${(Math.abs(drivers[i]) / Math.max(0.01, ...drivers.map(Math.abs))) * 79}%`,
                              }}
                            />
                            <span className={drivers[i] < 0 ? "negative-value" : ""}>
                              {drivers[i] > 0 ? "+" : "−"}
                              {Math.abs(drivers[i]).toFixed(1)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="driver-legend">
                      <span>
                        <i />
                        {l("Increases risk", "ঝুঁকি বাড়ায়")}
                      </span>
                      <span>
                        <i />
                        {l("Reduces risk", "ঝুঁকি কমায়")}
                      </span>
                    </div>
                    <div className="driver-insight">
                      <Sparkles size={15} />
                      <p>
                        {driverSentence(ward, week, horizon, lang)}
                      </p>
                    </div>
                  </section>
                </div>
                <div className="bottom-grid">
                  <section className="card scenario-card">
                    <CardHeader
                      title={t("scenarioTitle")}
                      subtitle={t("scenarioSub")}
                      action={
                        <span className="scenario-icon">
                          <CloudRain size={20} />
                        </span>
                      }
                    />
                    <div className="scenario-comparison">
                      <div className="scenario-pane">
                        <span className="scenario-eyebrow">
                          {t("baseline")}
                          <span>1.0×</span>
                        </span>
                        <div className="scenario-number">
                          {baseline.pred}
                          <small>{l("cases", "কেস")}</small>
                          <Badge tier={baseline.tier} small />
                        </div>
                        <p>
                          {l("80% range", "৮০% সীমা")}: {baseline.lo}–{baseline.hi}
                        </p>
                      </div>
                      <span className="scenario-arrow">
                        <ArrowRight size={17} />
                      </span>
                      <div className="scenario-pane selected-scenario">
                        <span className="scenario-eyebrow">
                          {t("scenario")}
                          <span>{times(multiplier)}×</span>
                        </span>
                        <div className="scenario-number">
                          {current.pred}
                          <small>{l("cases", "কেস")}</small>
                          <Badge tier={current.tier} small />
                        </div>
                        <p>
                          {l("80% range", "৮০% সীমা")}: {current.lo}–{current.hi}
                        </p>
                      </div>
                    </div>
                    <div className="scenario-footer">
                      {change === 0 ? (
                        <>
                          <span className="teal-dot" />
                          {l(
                            "At baseline. Adjust the rainfall slider to explore a different scenario.",
                            "মূল অবস্থায় আছে। ভিন্ন দৃশ্য দেখতে বৃষ্টিপাতের স্লাইডার বদলান।",
                          )}
                        </>
                      ) : (
                        <>
                          <TrendingUp size={13} />
                          {l(
                            `${Math.abs(change).toFixed(1)} ${change > 0 ? "more" : "fewer"} predicted cases${baseline.pred > 0 ? ` (${change > 0 ? "+" : ""}${Math.round((change / baseline.pred) * 100)}%)` : ""} compared with baseline.`,
                            `মূল অবস্থার তুলনায় ${Math.abs(change).toFixed(1)}টি কেস ${change > 0 ? "বেশি" : "কম"} হতে পারে।`,
                          )}
                        </>
                      )}
                    </div>
                  </section>
                  <section className="card context-card">
                    <CardHeader title={t("context")} subtitle={t("contextSub")} />
                    <div className="context-row">
                      <span className="context-icon">
                        <Waves size={16} />
                      </span>
                      <div>
                        <span>{l("Waterlogging susceptibility", "জলাবদ্ধতার ঝুঁকি")}</span>
                        <strong>
                          {info.waterlogging.toFixed(2)}
                          <small>/ 1.00</small>
                        </strong>
                      </div>
                      <span className="context-tag">{level(info.waterlogging)}</span>
                    </div>
                    <div className="context-row">
                      <span className="context-icon">
                        <MapPin size={16} />
                      </span>
                      <div>
                        <span>{l("Population density", "জনসংখ্যার ঘনত্ব")}</span>
                        <strong>
                          {info.density.toLocaleString()}
                          <small> / km²</small>
                        </strong>
                      </div>
                    </div>
                    <div className="context-row">
                      <span className="context-icon">
                        <ShieldCheck size={16} />
                      </span>
                      <div>
                        <span>{l("Sanitation score (higher is better)", "স্যানিটেশন স্কোর (বেশি হলে ভালো)")}</span>
                        <strong>
                          {info.sanitation.toFixed(2)}
                          <small>/ 1.00</small>
                        </strong>
                      </div>
                    </div>
                    <button className="text-link" onClick={() => setTab("validation")}>
                      {l("See how we validate this forecast", "এই পূর্বাভাসের যাচাই দেখুন")}
                      <ArrowUpRight size={14} />
                    </button>
                  </section>
                </div>
              </>
            )}
            {tab === "priority" && (
              <>
                <div className="section-topline">
                  <h2>
                    {l("A focused response starts here", "এখান থেকেই কার্যকর পদক্ষেপ")}
                    <span>
                      {" "}
                      · {WARDS.length} {l("wards", "ওয়ার্ড")}
                    </span>
                  </h2>
                  <button className="primary-button" onClick={downloadCsv}>
                    <ArrowDownToLine size={15} />
                    {t("download")}
                  </button>
                </div>
                <div className="kpi-grid tier-counts">
                  {(["Critical", "High", "Medium", "Low"] as Tier[]).map((tier) => (
                    <section className="card tier-count" key={tier}>
                      <Badge tier={tier} small />
                      <strong>
                        {ranked.filter((r) => r.tier === tier).length}
                        <span>{l("wards", "ওয়ার্ড")}</span>
                      </strong>
                      <p>
                        {tier === "Critical"
                          ? l("Immediate attention", "তাৎক্ষণিক নজর দিন")
                          : tier === "High"
                            ? l("Prioritize intervention", "হস্তক্ষেপে অগ্রাধিকার")
                            : tier === "Medium"
                              ? l("Increase surveillance", "নজরদারি বাড়ান")
                              : l("Continue monitoring", "পর্যবেক্ষণ অব্যাহত রাখুন")}
                      </p>
                    </section>
                  ))}
                </div>
                <section className="card table-card">
                  <CardHeader
                    title={t("tableTitle")}
                    subtitle={t("tableSub")}
                    action={
                      <span className="subtle-pill">
                        {horizon}w · {dateLabel(week, true)}
                      </span>
                    }
                  />
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          {[
                            t("rank"),
                            t("wardCol"),
                            t("risk"),
                            t("predicted"),
                            t("range"),
                            t("driver"),
                          ].map((c) => (
                            <th key={c}>{c}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {ranked.map((r, i) => (
                          <tr key={r.ward} className={r.ward === ward ? "selected-row" : ""}>
                            <td>
                              <span className="table-rank">{String(i + 1).padStart(2, "0")}</span>
                            </td>
                            <td>
                              <button
                                className="ward-link"
                                onClick={() => {
                                  setWard(r.ward);
                                  setTab("forecast");
                                }}
                              >
                                {r.ward}
                                <ArrowUpRight size={12} />
                              </button>
                            </td>
                            <td>
                              <Badge tier={r.tier} small />
                            </td>
                            <td>
                              <strong>{r.pred}</strong>
                            </td>
                            <td>
                              {r.lo} – {r.hi}
                            </td>
                            <td>
                              {topDriverLabel(r.ward, week, horizon, lang)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
                <section className="card heatmap-card">
                  <CardHeader
                    title={t("heatmap")}
                    subtitle={t("heatmapSub")}
                    action={
                      <div className="heatmap-legend">
                        {(["Low", "Medium", "High", "Critical"] as Tier[]).map((tier) => (
                          <Badge tier={tier} small key={tier} />
                        ))}
                      </div>
                    }
                  />
                  <div className="risk-heatmap">
                    <div className="heatmap-header">{t("wardCol")}</div>
                    {[2, 3, 4].map((h) => (
                      <div className="heatmap-header" key={h}>
                        {h} {l("weeks ahead", "সপ্তাহ পরে")}
                      </div>
                    ))}
                    {ranked.map((r) => (
                      <HeatmapRow
                        key={r.ward}
                        ward={r.ward}
                        week={week}
                        onSelect={(h) => {
                          setWard(r.ward);
                          setHorizon(h);
                          setTab("forecast");
                        }}
                      />
                    ))}
                  </div>
                </section>
              </>
            )}
            {tab === "validation" && (
              <Validation ward={ward} week={week} horizon={horizon} l={l} t={t} />
            )}
            {tab === "about" && <About l={l} t={t} />}
          </Guard>
          <footer className="main-footer">
            <div>
              <span className="footer-radar">
                <Radar size={13} />
              </span>
              {l("Better signals. Better preparedness.", "উন্নত সংকেত। উন্নত প্রস্তুতি।")}
            </div>
            <span>
              {l(
                "Built for public health, not for diagnosis.",
                "জনস্বাস্থ্যের জন্য, রোগ নির্ণয়ের জন্য নয়।",
              )}
              <span className="footer-dot">·</span>Moshari v2.0
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function HeatmapRow({
  ward,
  week,
  onSelect,
}: {
  ward: string;
  week: string;
  onSelect: (h: number) => void;
}) {
  return (
    <>
      <div className="heatmap-ward">{ward}</div>
      {[2, 3, 4].map((h) => {
        const f = forecast(ward, week, h);
        const c = TIER_COLORS[f.tier];
        return (
          <button
            onClick={() => onSelect(h)}
            key={h}
            style={{ background: c.bg, color: c.text, borderColor: c.border }}
          >
            <span>{f.tier}</span>
            <strong>{f.pred}</strong>
          </button>
        );
      })}
    </>
  );
}