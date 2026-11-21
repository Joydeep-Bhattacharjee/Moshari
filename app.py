"""DengueRadar PRD v2. Run: pip install -r requirements.txt; streamlit run app.py.

Artifact contract is documented in DENGUERADAR.md. All demo values are synthetic.
Only load trusted joblib artifacts: deserialization can execute arbitrary code.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

ROOT = Path(__file__).resolve().parent
TIERS = ["Low", "Medium", "High", "Critical"]
COLORS = {
    "Low": ("#E6F4F1", "#0072B2", "#083344"),
    "Medium": ("#FEF3C7", "#E69F00", "#451A03"),
    "High": ("#FFEDD5", "#D55E00", "#431407"),
    "Critical": ("#FDE2E4", "#800020", "#2B0608"),
}
GROUPS = ["Rain Lags 2–4w", "Rainfall Windows", "Temperature", "Humidity",
          "Ward Vulnerability", "Interactions", "Seasonality"]
TEXTS = {
    "en": {
        "title": "Small signals. Earlier action.", "subtitle": "Ward-level intelligence to stay ahead of dengue outbreaks.",
        "forecast": "Forecast", "priority": "Priority List", "validation": "Validation", "about": "About",
        "ward": "Ward", "week": "Forecast-Origin Week", "horizon": "Forecast Horizon",
        "rain": "What-If Rainfall Multiplier", "risk": "Risk Tier", "pred": "Predicted Cases",
        "range": "80% Range", "actual": "Target Week Actual", "pending": "Pending",
        "timeline": "Weather meets outbreak risk", "drivers": "What’s driving the risk?",
        "scenario": "What-If Scenario Comparison", "baseline": "Baseline", "scenario_name": "Scenario",
        "mock": "Mock Preview Mode", "live": "Live Model Loaded",
        "notice": "Realistic synthetic preview data. Not a public-health advisory.",
        "rank": "Rank", "top": "Top Driver", "download": "Download ranked CSV",
        "heatmap": "Ward × Horizon", "split": "Chronological split & purge gap",
        "performance": "Backtest & alert performance", "recall": "Alert Recall (High + Critical)",
        "precision": "Alert Precision", "coverage": "80% Coverage", "confusion": "Confusion Matrix",
        "lag": "Rainfall lag correlation (0–8 weeks)", "fit": "Predicted vs. Actual",
        "error": "This panel is unavailable. Check the artifact contract or choose another ward/week.",
        "demo_metrics": "Illustrative mock validation — these are not measured model results.",
        "no_validation": "No out-of-sample validation artifact was supplied. Metrics are not fabricated.",
        "actual_line": "Actual cases", "pred_line": "Predicted cases", "rain_line": "Rainfall (mm)",
        "band": "80% Uncertainty Band", "breeding": "2–4w Breeding Window",
    },
    "bn": {
        "title": "ক্ষুদ্র সংকেত। আগাম পদক্ষেপ।", "subtitle": "ডেঙ্গুর প্রাদুর্ভাবের আগেই প্রস্তুতির জন্য ওয়ার্ডভিত্তিক তথ্য।",
        "forecast": "পূর্বাভাস", "priority": "অগ্রাধিকার তালিকা", "validation": "যাচাই", "about": "পরিচিতি",
        "ward": "ওয়ার্ড", "week": "পূর্বাভাসের সূচনা সপ্তাহ", "horizon": "পূর্বাভাসের সময়সীমা",
        "rain": "সম্ভাব্য বৃষ্টিপাতের গুণক", "risk": "ঝুঁকির স্তর", "pred": "পূর্বাভাসিত কেস",
        "range": "৮০% সীমা", "actual": "লক্ষ্য সপ্তাহের প্রকৃত কেস", "pending": "অপেক্ষমাণ",
        "timeline": "আবহাওয়া ও প্রাদুর্ভাবের ঝুঁকি", "drivers": "ঝুঁকির পেছনের কারণ",
        "scenario": "বৃষ্টিপাতের সম্ভাব্য দৃশ্যের তুলনা", "baseline": "মূল পূর্বাভাস", "scenario_name": "সম্ভাব্য দৃশ্য",
        "mock": "নমুনা প্রিভিউ মোড", "live": "প্রকৃত মডেল সংযুক্ত",
        "notice": "বাস্তবসম্মত কৃত্রিম নমুনা তথ্য। এটি জনস্বাস্থ্য নির্দেশনা নয়।",
        "rank": "ক্রম", "top": "প্রধান কারণ", "download": "অগ্রাধিকার CSV ডাউনলোড",
        "heatmap": "ওয়ার্ড × সময়সীমা", "split": "সময়ানুক্রমিক বিভাজন ও বিরতি",
        "performance": "পূর্বাভাস ও সতর্কতার কার্যকারিতা", "recall": "সতর্কতা শনাক্তকরণ (High + Critical)",
        "precision": "সতর্কতার নির্ভুলতা", "coverage": "৮০% সীমার অন্তর্ভুক্তি", "confusion": "শ্রেণিবিন্যাসের সারণি",
        "lag": "বৃষ্টিপাতের সম্পর্ক (০–৮ সপ্তাহ ব্যবধান)", "fit": "পূর্বাভাসিত ও প্রকৃত কেস",
        "error": "এই অংশটি দেখানো যাচ্ছে না। আর্টিফ্যাক্টের কাঠামো দেখুন বা অন্য ওয়ার্ড ও সপ্তাহ বেছে নিন।",
        "demo_metrics": "নমুনা যাচাই — প্রকৃত মডেলের পরিমাপ নয়।",
        "no_validation": "স্বতন্ত্র যাচাইয়ের তথ্য দেওয়া হয়নি। কৃত্রিম পরিমাপ দেখানো হচ্ছে না।",
        "actual_line": "প্রকৃত কেস", "pred_line": "পূর্বাভাসিত কেস", "rain_line": "বৃষ্টিপাত (মিমি)",
        "band": "৮০% অনিশ্চয়তা সীমা", "breeding": "২–৪ সপ্তাহের প্রজননকাল",
    },
}


def label_text(en_str, bn_str, mode=None):
    mode = mode or st.session_state.get("lang_mode", "EN")
    return bn_str if mode == "বাংলা" else f"{en_str} / {bn_str}" if mode == "EN + বাংলা" else en_str


def text(key):
    return label_text(TEXTS["en"][key], TEXTS["bn"][key])


def tier_for(values, thresholds=(25, 50, 100)):
    return np.asarray(TIERS)[np.digitize(values, thresholds)]


@st.cache_data(show_spinner=False)
def build_mock_data():
    """Vectorized reproducible, weather-lagged synthetic ward history."""
    rng = np.random.default_rng(42)
    weeks = pd.date_range("2023-01-02", "2025-08-25", freq="W-MON")
    wards = np.array([f"Ward-{i:02}" for i in [1, 2, 4, 5, 7, 9, 12, 14, 16, 19, 21, 24]])
    frame = pd.MultiIndex.from_product([wards, weeks], names=["ward_id", "week"]).to_frame(index=False)
    n = len(frame)
    index = frame.ward_id.str[-2:].astype(int).to_numpy()
    season = np.sin(2 * np.pi * (frame.week.dt.dayofyear.to_numpy() - 100) / 365)
    frame["rainfall_mm"] = np.maximum(0, 65 + 55 * season + rng.normal(0, 27, n))
    frame["avg_temp_C"] = 27 + 4 * season + rng.normal(0, .8, n)
    frame["relative_humidity_pct"] = np.clip(71 + 15 * season + rng.normal(0, 4, n), 40, 99)
    frame["water_logging_risk_index"] = .25 + (index % 7) * .1
    frame["population_density_sqkm"] = 12000 + index * 700
    frame["sanitation_score"] = 85 - (index % 8) * 6
    for lag in range(9):
        frame[f"rain_lag_{lag}"] = frame.groupby("ward_id").rainfall_mm.shift(lag)
    frame = frame.dropna().reset_index(drop=True)
    frame["actual_cases"] = np.maximum(0, np.round(
        frame[["rain_lag_2", "rain_lag_3", "rain_lag_4"]].mean(axis=1) * .52
        + frame.water_logging_risk_index * 45 - frame.sanitation_score * .23
        + rng.normal(0, 7, len(frame))))
    return {
        "features": frame, "model": None, "is_mock_mode": True,
        "meta": {"trained_on": "2023-01-02 – 2024-12-30 (illustrative)", "tier_thresholds": [25, 50, 100],
                 "train_end": "2024-12-30", "validation_start": "2025-02-03",
                 "interval_relative_width": .25},
        "load_notice": None,
    }


@st.cache_resource(show_spinner=False)
def _load_model(path, signature):
    return joblib.load(path)


@st.cache_data(show_spinner=False)
def _load_files(meta_path, csv_path, signature):
    with open(meta_path, encoding="utf-8") as handle:
        meta = json.load(handle)
    frame = pd.read_csv(csv_path)
    frame["week"] = pd.to_datetime(frame["week"], errors="raise")
    return meta, frame


@st.cache_resource(show_spinner=False)
def _load_bundle(signature):
    model = _load_model(str(ROOT / "models/model.joblib"), signature)
    meta, frame = _load_files(str(ROOT / "models/meta.json"), str(ROOT / "data/processed/features.csv"), signature)
    required = ["ward_id", "week", "rainfall_mm", "avg_temp_C", "relative_humidity_pct",
                "water_logging_risk_index", "population_density_sqkm", "sanitation_score"]
    if not set(required).issubset(frame.columns) or frame.empty:
        raise ValueError("Missing required feature columns or empty dataset")
    columns = meta["feature_columns"]
    if not isinstance(columns, list) or not columns or not set(columns) <= set(frame.columns) | {"horizon"}:
        raise ValueError("Invalid feature_columns")
    if not callable(getattr(model, "predict", None)):
        raise ValueError("Model must implement predict")
    if frame[["ward_id", "week"]].isna().any().any() or frame.duplicated(["ward_id", "week"]).any():
        raise ValueError("Missing or duplicate ward/week keys")
    if frame.week.dt.dayofweek.nunique() != 1 or frame.week.dt.tz is not None:
        raise ValueError("Expected timezone-naive weekly dates on one weekday")
    for _, dates in frame.groupby("ward_id").week:
        if (dates.sort_values().diff().dropna().dt.days % 7 != 0).any():
            raise ValueError("Expected weekly dates")
    numeric = frame[[c for c in columns if c != "horizon"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("Model inputs must be finite numeric values")
    thresholds = np.asarray(meta.get("tier_thresholds", [25, 50, 100]), dtype=float)
    if len(thresholds) != 3 or not np.isfinite(thresholds).all() or not (np.diff(thresholds) > 0).all():
        raise ValueError("Invalid tier thresholds")
    if float(meta.get("interval_relative_width", .25)) <= 0:
        raise ValueError("Invalid interval width")
    if not set(meta.get("rainfall_scale_features", [])) <= set(columns):
        raise ValueError("Invalid rainfall scenario feature names")
    bundle = {"model": model, "meta": meta, "features": frame.sort_values(["ward_id", "week"]),
              "is_mock_mode": False, "load_notice": None}
    for h in (2, 3, 4):
        _predict(bundle, frame.tail(2), h, 1.0)
    return bundle


def load_dashboard_bundle():
    paths = [ROOT / p for p in ("models/model.joblib", "models/meta.json", "data/processed/features.csv")]
    try:
        signature = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
        return _load_bundle(signature)
    except Exception:
        bundle = build_mock_data()
        bundle["load_notice"] = "missing" if not all(p.exists() for p in paths) else "incompatible"
        return bundle


def _predict(bundle, rows, horizon, rain_multiplier):
    rows = rows.copy()
    meta = bundle["meta"]
    if bundle["is_mock_mode"]:
        rain = rows[["rain_lag_2", "rain_lag_3", "rain_lag_4"]].mean(axis=1).to_numpy()
        pred = np.maximum(1, (rain * .52 * (1 + .42 * (rain_multiplier - 1))
                              + rows.water_logging_risk_index.to_numpy() * 45
                              - rows.sanitation_score.to_numpy() * .23) * (1 + (horizon - 3) * .09))
    else:
        rows["horizon"] = horizon
        columns = meta["feature_columns"]
        rain_cols = meta.get("rainfall_scale_features", [])
        if rain_multiplier != 1 and not rain_cols:
            raise ValueError("rainfall_scale_features required for real-model scenarios")
        rows[rain_cols] = rows[rain_cols] * rain_multiplier
        pred = np.asarray(bundle["model"].predict(rows[columns]), dtype=float).reshape(-1)
        if len(pred) != len(rows) or not np.isfinite(pred).all():
            raise ValueError("Invalid model predictions")
        pred = np.maximum(0, pred)
    width = float(meta.get("interval_absolute_width", 0))
    if not width:
        width = pred * float(meta.get("interval_relative_width", .25))
    return np.round(pred).astype(int), np.floor(np.maximum(0, pred - width)).astype(int), np.ceil(pred + width).astype(int)


def _driver_impacts(bundle, row, horizon, multiplier):
    """Grouped reference ablation for real models; not SHAP or causal attribution."""
    if bundle["is_mock_mode"]:
        return np.array([22.4 * multiplier, 10.2 * multiplier, -6.4, 6.4,
                         float(row.water_logging_risk_index.iloc[0]) * 24, 3.8, -3.2])
    cols = bundle["meta"]["feature_columns"]
    mapping = bundle["meta"].get("driver_groups", {})
    if not mapping:
        return np.zeros(len(GROUPS))
    reference = bundle["meta"].get("reference_values", {})
    trials = pd.concat([row] * (len(GROUPS) + 1), ignore_index=True)
    for i, group in enumerate(GROUPS, 1):
        for column in mapping.get(group, []):
            if column in cols and column != "horizon":
                trials.loc[i, column] = reference.get(column, bundle["features"][column].median())
    pred, _, _ = _predict(bundle, trials, horizon, multiplier)
    return pred[0] - pred[1:]


def get_ward_forecast(bundle, ward, week, horizon, rain_multiplier):
    frame = bundle["features"]
    week = pd.Timestamp(week)
    row = frame[(frame.ward_id == ward) & (frame.week == week)]
    if row.empty:
        raise ValueError("No ward observation for selected week")
    pred, lo, hi = _predict(bundle, row, horizon, rain_multiplier)
    target = week + pd.Timedelta(weeks=horizon)
    actual = frame.loc[(frame.ward_id == ward) & (frame.week == target), "actual_cases"] if "actual_cases" in frame else pd.Series(dtype=float)
    history = frame[(frame.ward_id == ward) & (frame.week <= week)].tail(26).copy()
    p, lower, upper = _predict(bundle, history, horizon, rain_multiplier)
    history["week"] = history.week + pd.Timedelta(weeks=horizon)
    history["rainfall_mm"] = history.rainfall_mm * rain_multiplier
    lookup = frame[frame.ward_id == ward].set_index("week")
    history["actual_cases"] = history.week.map(lookup.actual_cases) if "actual_cases" in lookup else np.nan
    history["pred_cases"], history["lo"], history["hi"] = p, lower, upper
    # Rainfall aligned to target dates, not forecast-origin dates.
    history["rainfall_mm"] = history.week.map(lookup.rainfall_mm) * rain_multiplier
    impacts = _driver_impacts(bundle, row, horizon, rain_multiplier)
    order = np.argsort(-impacts)
    top = GROUPS[order[0]] if np.any(impacts) else None
    summary_en = (f"{top} is the strongest risk-increasing driver for this {horizon}-week forecast."
                  if top else "Driver attribution is unavailable; add driver_groups to the model metadata.")
    bn_names = ["২–৪ সপ্তাহ আগের বৃষ্টি", "বৃষ্টিপাতের সময়কাল", "তাপমাত্রা", "আর্দ্রতা", "ওয়ার্ডের ঝুঁকিপ্রবণতা", "পারস্পরিক প্রভাব", "ঋতুগত প্রভাব"]
    summary_bn = (f"{bn_names[order[0]]} এই {horizon} সপ্তাহের পূর্বাভাসে ঝুঁকি বৃদ্ধির প্রধান প্রভাবক।"
                  if top else "প্রভাবকের তথ্য নেই; মডেলের মেটাডেটায় driver_groups যোগ করুন।")
    scenario_rows = []
    for mult in np.round(np.arange(.5, 2.01, .1), 1):
        if not bundle["is_mock_mode"] and not bundle["meta"].get("rainfall_scale_features") and mult != 1:
            continue
        sp, sl, sh = _predict(bundle, row, horizon, mult)
        scenario_rows.append({"multiplier": mult, "pred_cases": sp[0], "lo": sl[0], "hi": sh[0],
                              "tier": tier_for(sp, bundle["meta"].get("tier_thresholds", [25, 50, 100]))[0]})
    return {"tier": tier_for(pred, bundle["meta"].get("tier_thresholds", [25, 50, 100]))[0],
            "pred_cases": int(pred[0]), "lo": int(lo[0]), "hi": int(hi[0]),
            "actual_cases": None if actual.empty or pd.isna(actual.iloc[0]) else int(actual.iloc[0]),
            "target_week": target, "drivers": pd.DataFrame({"group": GROUPS, "impact": impacts}),
            "summary_en": summary_en, "summary_bn": summary_bn,
            "series": history[["week", "rainfall_mm", "actual_cases", "pred_cases", "lo", "hi"]],
            "scenarios": pd.DataFrame(scenario_rows)}


def get_priority_table(bundle, week, horizon):
    rows = bundle["features"].loc[bundle["features"].week == pd.Timestamp(week)].copy()
    matrix = pd.DataFrame(index=rows.ward_id)
    for h in (2, 3, 4):
        p, lo, hi = _predict(bundle, rows, h, 1)
        tiers = tier_for(p, bundle["meta"].get("tier_thresholds", [25, 50, 100]))
        matrix[f"{h}w"] = tiers
        if h == horizon:
            table = pd.DataFrame({"ward_id": rows.ward_id.to_numpy(), "tier": tiers,
                                  "pred_cases": p, "lo": lo, "hi": hi})
    # Attribution must not invent per-ward drivers for an unexplained real model.
    table["top_driver"] = "Rain Lags 2–4w" if bundle["is_mock_mode"] else "Not supplied"
    mapping = bundle["meta"].get("driver_groups", {})
    if not bundle["is_mock_mode"] and mapping:
        count = len(rows)
        trials = pd.concat([rows] * (len(GROUPS) + 1), ignore_index=True)
        for i, group in enumerate(GROUPS, 1):
            for column in mapping.get(group, []):
                if column in bundle["meta"]["feature_columns"] and column != "horizon":
                    reference = bundle["meta"].get("reference_values", {}).get(column, bundle["features"][column].median())
                    trials.loc[i * count:(i + 1) * count - 1, column] = reference
        predictions, _, _ = _predict(bundle, trials, horizon, 1)
        predictions = predictions.reshape(len(GROUPS) + 1, count)
        impacts = predictions[0] - predictions[1:]
        table["top_driver"] = np.where(np.any(impacts != 0, axis=0),
                                      np.asarray(GROUPS)[impacts.argmax(axis=0)], "Not supplied")
    table["_order"] = pd.Categorical(table.tier, categories=TIERS[::-1], ordered=True)
    table = table.sort_values(["_order", "pred_cases"], ascending=[True, False]).drop(columns="_order").reset_index(drop=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table, matrix.loc[table.ward_id]


def get_validation_data(bundle, ward):
    """Real metrics require genuine held-out rows; demo backtests are labeled."""
    frame = bundle["features"].query("ward_id == @ward").sort_values("week")
    lag = pd.DataFrame({"lag": range(9), "correlation": [
        frame.rainfall_mm.shift(i).corr(frame.actual_cases) if "actual_cases" in frame else np.nan for i in range(9)]})
    split = {"train_end": bundle["meta"].get("train_end", "Not supplied"),
             "validation_start": bundle["meta"].get("validation_start", "Not supplied"), "purge_weeks": 4}
    if not bundle["is_mock_mode"]:
        validation = bundle["meta"].get("validation", {})
        return {"split": split, "lag_correlation": lag, "available": bool(validation), **validation}
    fit = frame[frame.week >= "2025-02-03"].copy()
    actual = fit.actual_cases.to_numpy()
    # Synthetic out-of-sample-like errors, not training/inference performance.
    predicted = np.maximum(0, actual + 9 * np.sin(np.arange(len(fit)) * 1.7) + 4)
    fit["pred_cases"], fit["lo"], fit["hi"] = predicted, np.maximum(0, predicted - 12), predicted + 12
    alert, forecast_alert = actual >= 50, predicted >= 50
    tp, fp = int((alert & forecast_alert).sum()), int((~alert & forecast_alert).sum())
    fn, tn = int((alert & ~forecast_alert).sum()), int((~alert & ~forecast_alert).sum())
    folds = pd.DataFrame({"fold": ["Fold 1", "Fold 2", "Fold 3", "Fold 4"],
                          "MAE": [9.2, 8.6, 8.1, 7.7], "RMSE": [13.1, 12.3, 11.8, 11.2]})
    comparison = pd.DataFrame({"Model": ["Last-week baseline", "Seasonal baseline", "DengueRadar"],
                               "MAE": [17.2, 14.7, 8.4], "RMSE": [23.6, 20.2, 12.1]})
    return {"available": True, "split": split, "folds": folds, "comparison": comparison,
            "alert_recall": tp / max(1, tp + fn), "alert_precision": tp / max(1, tp + fp),
            "coverage": float(((actual >= fit.lo) & (actual <= fit.hi)).mean()),
            "confusion_matrix": [[tn, fp], [fn, tp]], "lag_correlation": lag, "fit": fit}


def badge(tier):
    bg, border, fg = COLORS[tier]
    st.markdown(f'<span style="display:inline-block;background:{bg};color:{fg};border:1px solid {border};border-radius:5px;padding:5px 12px;font-weight:600">● {tier}</span>', unsafe_allow_html=True)


@contextmanager
def guarded():
    try:
        yield
    except Exception:
        st.warning(text("error"))


def plot(fig, height=320):
    fig.update_layout(height=height, margin=dict(l=20, r=20, t=35, b=25),
                      paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#475569", size=11),
                      legend=dict(orientation="h", y=-.2), hovermode="x unified")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#F1F5F9", zeroline=False)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def line_figure(frame):
    frame = pd.DataFrame(frame)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame.week, y=frame.lo, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=frame.week, y=frame.hi, fill="tonexty", fillcolor="rgba(59,130,246,.16)", line=dict(width=0), name=text("band"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=frame.week, y=frame.actual_cases, name=text("actual_line"), line=dict(color="#1E293B", width=2.5)))
    fig.add_trace(go.Scatter(x=frame.week, y=frame.pred_cases, name=text("pred_line"), line=dict(color="#258B82", width=2, dash="dot")))
    return fig


def render_forecast(bundle, ward, week, horizon, multiplier):
    forecast = get_ward_forecast(bundle, ward, week, horizon, multiplier)
    st.subheader(f"{ward} · {horizon}w")
    st.caption(f'{text("actual")}: {forecast["target_week"]:%d %b %Y}')
    columns = st.columns(4)
    with columns[0]:
        with st.container(border=True):
            st.caption(text("risk"))
            badge(forecast["tier"])
    for column, key, value in zip(columns[1:], ["pred", "range", "actual"],
                                  [forecast["pred_cases"], f'{forecast["lo"]} – {forecast["hi"]}',
                                   forecast["actual_cases"] if forecast["actual_cases"] is not None else text("pending")]):
        with column:
            with st.container(border=True):
                st.metric(text(key), value)
    left, right = st.columns([1.6, 1])
    with left, st.container(border=True):
        st.subheader(text("timeline"))
        history = forecast["series"]
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=history.week, y=history.rainfall_mm, name=text("rain_line"), marker_color="#56B4E9", opacity=.4), secondary_y=True)
        for trace in line_figure(history).data:
            fig.add_trace(trace, secondary_y=False)
        fig.add_vrect(x0=pd.Timestamp(week) - pd.Timedelta(weeks=4), x1=pd.Timestamp(week) - pd.Timedelta(weeks=2),
                      fillcolor="rgba(230,159,0,.14)", line_width=0, annotation_text=text("breeding"))
        fig.update_yaxes(title_text=label_text("Cases", "কেস"), secondary_y=False)
        fig.update_yaxes(title_text="mm", showgrid=False, secondary_y=True)
        plot(fig, 350)
    with right, st.container(border=True):
        st.subheader(text("drivers"))
        drivers = forecast["drivers"].iloc[::-1]
        bn_groups = ["২–৪ সপ্তাহ আগের বৃষ্টি", "বৃষ্টিপাতের সময়কাল", "তাপমাত্রা", "আর্দ্রতা", "ওয়ার্ডের ঝুঁকিপ্রবণতা", "পারস্পরিক প্রভাব", "ঋতুগত প্রভাব"]
        translated = dict(zip(GROUPS, bn_groups))
        fig = go.Figure(go.Bar(x=drivers.impact, y=[label_text(g, translated[g]) for g in drivers.group],
                              orientation="h", marker_color=np.where(drivers.impact >= 0, "#D55E00", "#0072B2"),
                              text=[f"{x:+.1f}" for x in drivers.impact], textposition="outside"))
        plot(fig, 275)
        st.info(label_text(forecast["summary_en"], forecast["summary_bn"]))
        st.caption(label_text("Illustrative contributions." if bundle["is_mock_mode"] else "Reference ablations, not causal effects or additive SHAP values.",
                              "নমুনা অবদান।" if bundle["is_mock_mode"] else "রেফারেন্সভিত্তিক অবদান; কারণ-ফল বা SHAP নয়।"))
    with st.container(border=True):
        st.subheader(text("scenario"))
        base = get_ward_forecast(bundle, ward, week, horizon, 1)
        for column, name, mult, result in zip(st.columns(2), ["baseline", "scenario_name"], [1, multiplier], [base, forecast]):
            with column:
                st.caption(f"{text(name)} · {mult:.1f}×")
                st.metric(text("pred"), result["pred_cases"])
                st.caption(f'{text("range")}: {result["lo"]} – {result["hi"]}')
                badge(result["tier"])
        st.caption(label_text("Explore 0.5×–2.0× rainfall using the sidebar slider. Other inputs stay fixed.",
                              "পাশের স্লাইডারে বৃষ্টিপাত ০.৫×–২.০× বদলান। অন্য তথ্য অপরিবর্তিত থাকে।"))


def render_priority(bundle, week, horizon):
    table, matrix = get_priority_table(bundle, week, horizon)
    for col, tier in zip(st.columns(4), TIERS[::-1]):
        with col, st.container(border=True):
            badge(tier)
            st.metric(text("ward"), int((table.tier == tier).sum()))
    st.subheader(text("priority"))
    visible = table.assign(interval=table.lo.astype(str) + " – " + table.hi.astype(str))
    names = {"rank": text("rank"), "ward_id": text("ward"), "tier": text("risk"),
             "pred_cases": text("pred"), "interval": text("range"), "top_driver": text("top")}
    visible = visible[list(names)].rename(columns=names)
    st.dataframe(visible, hide_index=True, use_container_width=True)
    st.download_button(text("download"), visible.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"spray-priority-{week:%Y-%m-%d}-{horizon}w.csv", mime="text/csv")
    st.subheader(text("heatmap"))
    encoded = matrix.replace({tier: i for i, tier in enumerate(TIERS)}).to_numpy(dtype=float)
    scale = [[0, COLORS["Low"][0]], [.249, COLORS["Low"][0]], [.25, COLORS["Medium"][0]],
             [.499, COLORS["Medium"][0]], [.5, COLORS["High"][0]], [.749, COLORS["High"][0]],
             [.75, COLORS["Critical"][0]], [1, COLORS["Critical"][0]]]
    fig = go.Figure(go.Heatmap(z=encoded, x=matrix.columns, y=matrix.index, text=matrix.to_numpy(),
                              texttemplate="%{text}", colorscale=scale, zmin=0, zmax=3,
                              showscale=False, xgap=4, ygap=4, hovertemplate="%{y} · %{x}: %{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    plot(fig, max(380, len(matrix) * 34))


def render_validation(bundle, ward):
    data = get_validation_data(bundle, ward)
    st.subheader(text("split"))
    split = data["split"]
    st.info(label_text(f'Train through {split["train_end"]}; 4-week purge gap; validate from {split["validation_start"]}. Four chronological walk-forward folds; never shuffle.',
                       f'প্রশিক্ষণ শেষ {split["train_end"]}; ৪ সপ্তাহ বিরতি; যাচাই শুরু {split["validation_start"]}। সময়ানুক্রমিক চার ধাপে যাচাই; এলোমেলো বিভাজন নয়।'))
    if bundle["is_mock_mode"]:
        st.warning(text("demo_metrics"))
    if not data["available"]:
        st.info(text("no_validation"))
    else:
        st.dataframe(pd.DataFrame(data["comparison"]), hide_index=True, use_container_width=True)
        st.subheader(text("performance"))
        for col, key in zip(st.columns(3), ["alert_recall", "alert_precision", "coverage"]):
            with col, st.container(border=True):
                st.metric(text({"alert_recall": "recall", "alert_precision": "precision", "coverage": "coverage"}[key]), f'{data[key]:.1%}')
        left, right = st.columns(2)
        with left, st.container(border=True):
            folds = pd.DataFrame(data["folds"])
            fig = go.Figure()
            for metric, color in [("MAE", "#258B82"), ("RMSE", "#56B4E9")]:
                fig.add_bar(x=folds.fold, y=folds[metric], name=metric, marker_color=color)
            fig.update_layout(barmode="group")
            plot(fig)
        with right, st.container(border=True):
            st.subheader(text("confusion"))
            labels = [label_text("Low / Medium", "কম / মাঝারি"), "High / Critical"]
            fig = go.Figure(go.Heatmap(z=data["confusion_matrix"], x=labels, y=labels, texttemplate="%{z}", colorscale="Blues", showscale=False))
            fig.update_xaxes(title_text=label_text("Predicted", "পূর্বাভাসিত"))
            fig.update_yaxes(title_text=label_text("Actual", "প্রকৃত"), autorange="reversed")
            plot(fig, 280)
        st.subheader(f'{ward} · {text("fit")}')
        fit = pd.DataFrame(data["fit"])
        fit["week"] = pd.to_datetime(fit.week)
        plot(line_figure(fit), 340)
    st.subheader(text("lag"))
    lag = pd.DataFrame(data["lag_correlation"])
    plot(go.Figure(go.Bar(x=lag.lag, y=lag.correlation, marker_color=["#258B82" if 2 <= x <= 4 else "#56B4E9" for x in lag.lag])))


def render_about(bundle):
    st.subheader("DengueRadar · PRD v2")
    bullets = [
        ("Multi-week rainfall, temperature, and humidity lags capture conditions before outbreaks.", "বৃষ্টিপাত, তাপমাত্রা ও আর্দ্রতার কয়েক সপ্তাহের তথ্য প্রাদুর্ভাবের আগের পরিস্থিতি ধরতে সাহায্য করে।"),
        ("Waterlogging, population density, and sanitation capture hyper-local ward vulnerability.", "জলাবদ্ধতা, জনঘনত্ব ও স্যানিটেশন ওয়ার্ডের স্থানীয় ঝুঁকি চিহ্নিত করে।"),
        ("Forecast 2, 3, and 4 weeks ahead, with explicit risk tiers and 80% prediction intervals.", "২, ৩ ও ৪ সপ্তাহ আগাম ঝুঁকি ও ৮০% পূর্বাভাস সীমা দেখুন।"),
        ("Rank spray-team priorities and explore 0.5×–2.0× rainfall scenarios without external calls.", "বাহ্যিক যোগাযোগ ছাড়াই স্প্রে দলের অগ্রাধিকার ও বৃষ্টিপাতের সম্ভাব্য প্রভাব দেখুন।"),
        ("Chronological validation uses a 4-week purge gap and walk-forward alert evaluation.", "সময়ানুক্রমিক যাচাইয়ে ৪ সপ্তাহ বিরতি ও ধাপে ধাপে সতর্কতা মূল্যায়ন ব্যবহার করা হয়।"),
    ]
    for en, bn in bullets:
        st.markdown(f"- {label_text(en, bn)}")
    if bundle["is_mock_mode"]:
        st.warning(label_text("Mock Preview Mode: backend artifacts and the feature pipeline are in progress. All model outputs and metrics shown are synthetic.",
                              "নমুনা প্রিভিউ: ব্যাকএন্ড ও ফিচার পাইপলাইনের কাজ চলছে। প্রদর্শিত সব মডেল ফল ও পরিমাপ কৃত্রিম।"))
    st.info(f'0 API calls, 0 LLM tokens, model trained on {bundle["meta"].get("trained_on", "dates not supplied")}')
    st.caption(label_text("Planning support only, not diagnosis. Uncertainty bands are estimates; real coverage must be assessed out of sample.",
                          "শুধু পরিকল্পনায় সহায়তা, রোগ নির্ণয় নয়। প্রকৃত নির্ভরযোগ্যতা স্বতন্ত্র তথ্য দিয়ে যাচাই করতে হবে।"))


def main():
    st.set_page_config(page_title="DengueRadar · Early Warning", page_icon="D", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""<style>
      .stApp{background:#F8FAFC;color:#0F172A}
      [data-testid="stSidebar"]{background:white;border-right:1px solid #E2E8F0}
      [data-testid="stVerticalBlockBorderWrapper"]>div{background:white;border-radius:10px;border-color:#E2E8F0!important}
      h1,h2,h3{letter-spacing:-.5px} h3{font-size:1.1rem!important}
      [data-testid="stMetricValue"]{font-size:2rem} .stCaption{color:#475569}
      .block-container{padding-top:2rem}
    </style>""", unsafe_allow_html=True)
    bundle = load_dashboard_bundle()
    with st.sidebar:
        st.markdown("## DengueRadar")
        st.caption("ANTICIPATE. ACT. PROTECT.")
        st.selectbox("Language / ভাষা", ["EN", "বাংলা", "EN + বাংলা"], key="lang_mode")
        frame = bundle["features"]
        wards = sorted(frame.ward_id.unique())
        ward = st.selectbox(text("ward"), wards, index=wards.index("Ward-07") if "Ward-07" in wards else 0)
        weeks = sorted(frame.loc[frame.ward_id == ward, "week"].unique(), reverse=True)
        week = pd.Timestamp(st.selectbox(text("week"), weeks, format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y")))
        horizon = st.radio(text("horizon"), [2, 3, 4], index=1, horizontal=True, format_func=lambda h: f"{h}w")
        supported = bundle["is_mock_mode"] or bool(bundle["meta"].get("rainfall_scale_features"))
        multiplier = st.slider(text("rain"), .5, 2.0, 1.0, .1, disabled=not supported)
        if not supported:
            st.caption(label_text("Scenarios require rainfall_scale_features in meta.json.", "সম্ভাব্য দৃশ্য দেখতে meta.json-এ rainfall_scale_features প্রয়োজন।"))
        st.divider()
        st.caption(label_text("A planning tool, not a certainty. Use alongside local surveillance.", "পরিকল্পনার সহায়ক, নিশ্চয়তা নয়। স্থানীয় নজরদারির সঙ্গে ব্যবহার করুন।"))
    left, right = st.columns([4, 1])
    with left:
        st.title(text("title"))
        st.caption(text("subtitle"))
    with right:
        st.info(text("mock" if bundle["is_mock_mode"] else "live"))
    if bundle["is_mock_mode"]:
        st.caption(text("notice"))
        if bundle["load_notice"] == "incompatible":
            st.warning(label_text("Artifacts could not be loaded safely. Showing mock data. See DENGUERADAR.md for the expected schema.",
                                  "আর্টিফ্যাক্ট লোড করা যায়নি। নমুনা তথ্য দেখানো হচ্ছে। কাঠামোর জন্য DENGUERADAR.md দেখুন।"))
    elif "interval_absolute_width" not in bundle["meta"]:
        st.caption(label_text("80% intervals use an uncalibrated relative-width fallback; empirical coverage is not guaranteed.",
                              "৮০% সীমায় অপরিমাপিত আনুপাতিক প্রস্থ ব্যবহৃত; প্রকৃত অন্তর্ভুক্তি নিশ্চিত নয়।"))
    tabs = st.tabs([text(k) for k in ["forecast", "priority", "validation", "about"]])
    with tabs[0], guarded():
        render_forecast(bundle, ward, week, horizon, multiplier)
    with tabs[1], guarded():
        render_priority(bundle, week, horizon)
    with tabs[2], guarded():
        render_validation(bundle, ward)
    with tabs[3], guarded():
        render_about(bundle)
    st.caption(label_text("Better signals. Better preparedness. · DengueRadar v2.0 · Built for public health, not diagnosis.",
                          "উন্নত সংকেত। উন্নত প্রস্তুতি। · ডেঙ্গুরাডার v2.0 · জনস্বাস্থ্যের জন্য, রোগ নির্ণয়ের জন্য নয়।"))


if __name__ == "__main__":
    main()
