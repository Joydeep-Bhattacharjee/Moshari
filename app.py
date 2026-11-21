"""Moshari dashboard: ward-level dengue early warning (PRD section 7).

Run: streamlit run app.py
Everything runs locally from the saved model: 0 API calls, 0 LLM tokens.
"""
from __future__ import annotations

import html
import json
import time

import pandas as pd
import streamlit as st

from src import config as cfg
from src.charts import (
    TIER_COLORS,
    TIER_TEXT_COLORS,
    confusion_chart,
    driver_chart,
    fold_error_chart,
    holdout_series_chart,
    importance_chart,
    lag_chart,
    rain_cases_chart,
    split_timeline,
    tier_heatmap,
)
from src.data import load_weekly
from src.predict import ForecastError, load_bundle, load_feature_frame, predict_all_wards, predict_one, valid_dates
from src.report import build_report
from src.scenario import MULTIPLIER_RANGE, run_scenario
from src.tiers import TIERS

HISTORY_WEEKS = 26
DEFAULT_WARD = "DSCC_Ward_05"
DEFAULT_HORIZON = 3

CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1280px;}
h1, h2, h3 {font-family: Georgia, 'Times New Roman', serif; letter-spacing: -0.01em;}
.m-kicker {text-transform: uppercase; letter-spacing: .16em; font-size: .72rem; color: #6B7780;}
.m-title {font-family: Georgia, serif; font-size: 2.7rem; line-height: 1.02; margin: .1rem 0 .3rem;}
.m-sub {color: #4A5560; font-size: .95rem; margin-bottom: 1.2rem;}
.m-caption {font-size: .72rem; color: #6B7780; text-transform: uppercase; letter-spacing: .12em; margin-bottom: .35rem;}
.m-badge {display: inline-block; padding: .5rem 1.1rem; border-radius: 3px; font-family: Georgia, serif;
          font-size: 1.55rem; font-weight: 700; letter-spacing: .04em;
          box-shadow: 0 1px 0 rgba(0,0,0,.06), 0 10px 22px -14px rgba(0,0,0,.45);}
.m-reason {border-left: 4px solid #0F5257; background: #F1ECE3; padding: .85rem 1.1rem;
           font-size: 1.05rem; margin: .4rem 0 1.1rem; font-family: Georgia, serif;}
.m-count {border-radius: 3px; padding: .7rem 1rem .6rem;}
.m-count b {display: block; font-family: Georgia, serif; font-size: 2rem; line-height: 1;}
.m-footer {color: #6B7780; font-size: .8rem; border-top: 1px solid #D9D2C5; padding-top: .7rem; margin-top: 2.2rem;}
</style>
"""


# --- cached loaders (model once per process, data once per model version) -------------------
@st.cache_resource(show_spinner="Loading model…")
def get_bundle() -> dict:
    return load_bundle()


@st.cache_data(show_spinner="Building features…")
def get_frame(_bundle: dict, trained_at: str) -> pd.DataFrame:
    return load_feature_frame(_bundle)


@st.cache_data
def get_weekly() -> pd.DataFrame:
    return load_weekly()


@st.cache_data
def get_meta() -> dict:
    return json.loads(cfg.META_PATH.read_text(encoding="utf-8"))


@st.cache_data
def get_all_wards(_frame: pd.DataFrame, _bundle: dict, trained_at: str, date, horizon: int) -> pd.DataFrame:
    return predict_all_wards(_frame, _bundle, date, horizon)


# --- small HTML pieces ----------------------------------------------------------------------
def tier_badge(tier: str, caption: str) -> str:
    style = f"background:{TIER_COLORS[tier]};color:{TIER_TEXT_COLORS[tier]}"
    return f"<div class='m-caption'>{html.escape(caption)}</div><span class='m-badge' style='{style}'>{tier.upper()}</span>"


def tier_count(tier: str, count: int) -> str:
    style = f"background:{TIER_COLORS[tier]};color:{TIER_TEXT_COLORS[tier]}"
    return f"<div class='m-count' style='{style}'><b>{count}</b>{tier} wards</div>"


def _tier_cell(tier) -> str:
    if tier not in TIER_COLORS:
        return ""
    return f"background-color: {TIER_COLORS[tier]}; color: {TIER_TEXT_COLORS[tier]}; font-weight: 600"


def _safe(render) -> None:
    """Show problems as a warning in the page, never as a traceback."""
    try:
        render()
    except ForecastError as exc:
        st.warning(str(exc))
    except Exception as exc:  # last line of defence for the UI
        st.warning(f"This view could not be drawn: {exc}")


# --- layout ---------------------------------------------------------------------------------
def sidebar(frame: pd.DataFrame, weekly: pd.DataFrame) -> tuple[str, pd.Timestamp, int, float]:
    wards = weekly[[cfg.WARD_COL, cfg.CITY_COL]].drop_duplicates().sort_values(cfg.WARD_COL)
    labels = dict(zip(wards[cfg.WARD_COL], wards[cfg.WARD_COL] + " · " + wards[cfg.CITY_COL]))
    ward_ids = list(labels)
    st.sidebar.markdown("### Forecast settings")
    ward = st.sidebar.selectbox(
        "Ward", ward_ids, index=ward_ids.index(DEFAULT_WARD) if DEFAULT_WARD in ward_ids else 0,
        format_func=labels.get,
    )
    dates = valid_dates(frame)
    date = st.sidebar.select_slider(
        "Forecast week (Monday)", options=dates, value=dates[-1], format_func=lambda d: d.strftime("%d %b %Y")
    )
    horizon = st.sidebar.radio(
        "Look ahead", cfg.HORIZONS, index=cfg.HORIZONS.index(DEFAULT_HORIZON),
        format_func=lambda h: f"{h} weeks", horizontal=True,
    )
    multiplier = st.sidebar.slider("What-if: rain in the last 4 weeks ×", *MULTIPLIER_RANGE, 1.0, 0.25)
    st.sidebar.caption("Tip: the latest week is dry season. Slide back to a monsoon week (Jun–Oct) to see alerts.")
    return ward, date, horizon, multiplier


def header(date: pd.Timestamp, horizon: int) -> None:
    st.markdown(
        "<div class='m-kicker'>Ward-level dengue early warning</div>"
        "<div class='m-title'>Moshari</div>"
        f"<div class='m-sub'>Forecast made {date:%d %b %Y} · looking {horizon} weeks ahead · "
        "60 wards across Dhaka North, Dhaka South, Chattogram, Gazipur and Narayanganj</div>",
        unsafe_allow_html=True,
    )


def _ward_history(weekly: pd.DataFrame, ward: str, origin: pd.Timestamp, target: pd.Timestamp) -> pd.DataFrame:
    start = origin - pd.Timedelta(weeks=HISTORY_WEEKS)
    rows = weekly[(weekly[cfg.WARD_COL] == ward) & weekly[cfg.DATE_COL].between(start, target)]
    return rows.rename(columns={cfg.DATE_COL: "date", cfg.RAIN_COL: "rain", cfg.TARGET_COL: "cases"})


def forecast_tab(frame, bundle, weekly, ward, date, horizon, multiplier) -> None:
    start = time.perf_counter()
    result = predict_one(frame, bundle, ward, date, horizon)
    elapsed_ms = (time.perf_counter() - start) * 1000
    badge, cases, band, week, actual = st.columns([1.4, 1, 1, 1, 1.2])
    badge.markdown(tier_badge(result["tier"], f"Risk in {horizon} weeks"), unsafe_allow_html=True)
    cases.metric("Predicted cases", f"{result['predicted_cases']:.1f}")
    band.metric("80% range", f"{result['low_80']:.1f} – {result['high_80']:.1f}")
    week.metric("For the week of", f"{result['target_week']:%d %b %Y}")
    known = not pd.isna(result["actual_cases"])
    actual.metric("What happened", f"{result['actual_cases']:.0f} ({result['actual_tier']})" if known else "not yet known")
    st.markdown(f"<div class='m-reason'>{html.escape(result['sentence'])}</div>", unsafe_allow_html=True)
    left, right = st.columns([1, 1.5])
    left.plotly_chart(driver_chart(result["impacts"]), use_container_width=True)
    history = _ward_history(weekly, ward, pd.Timestamp(date), result["target_week"])
    right.plotly_chart(rain_cases_chart(history, date, result["target_week"], result), use_container_width=True)
    if multiplier != 1.0:
        scenario_block(weekly, bundle, ward, date, horizon, multiplier)
    st.caption(f"Forecast computed in {elapsed_ms:.0f} ms on this machine · no external calls.")


def scenario_block(weekly, bundle, ward, date, horizon, multiplier) -> None:
    result = run_scenario(weekly, bundle, ward, date, horizon, multiplier)
    st.markdown(f"### What if the last 4 weeks had {multiplier:g}× the rain?")
    before, after, change = st.columns(3)
    before.markdown(tier_badge(result["baseline"]["tier"], "As observed"), unsafe_allow_html=True)
    before.caption(f"{result['baseline']['predicted_cases']:.1f} cases expected")
    after.markdown(tier_badge(result["scenario"]["tier"], f"With {multiplier:g}× rain"), unsafe_allow_html=True)
    after.caption(f"{result['scenario']['predicted_cases']:.1f} cases expected")
    change.metric("Change", f"{result['change_cases']:+.1f} cases")


def priority_tab(frame, bundle, date, horizon) -> None:
    trained_at = bundle["trained_at"]
    table = get_all_wards(frame, bundle, trained_at, date, horizon)
    counts = table["tier"].value_counts()
    for tier, col in zip(reversed(TIERS), st.columns(len(TIERS))):
        col.markdown(tier_count(tier, int(counts.get(tier, 0))), unsafe_allow_html=True)
    st.markdown(f"### Where to send spray teams first · forecast for {horizon} weeks ahead")
    columns = ["rank", cfg.WARD_COL, cfg.CITY_COL, "tier", "predicted_cases", "low_80", "high_80", "top_driver", "actual_cases"]
    styled = table[columns].style.map(_tier_cell, subset=["tier"]).format(
        {"predicted_cases": "{:.1f}", "low_80": "{:.1f}", "high_80": "{:.1f}", "actual_cases": "{:.0f}"}, na_rep="—"
    )
    st.dataframe(styled, hide_index=True, use_container_width=True, height=420)
    csv = build_report(frame, bundle, date, horizon).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download spray-team plan (CSV)", csv, file_name=f"spray_plan_{date:%Y-%m-%d}_h{horizon}.csv", mime="text/csv"
    )
    grid = pd.concat([get_all_wards(frame, bundle, trained_at, date, h).assign(horizon=h) for h in cfg.HORIZONS])
    order = {w: i for i, w in enumerate(table[cfg.WARD_COL])}
    grid = grid.assign(order=grid[cfg.WARD_COL].map(order)).sort_values(["order", "horizon"])
    st.plotly_chart(tier_heatmap(grid.rename(columns={cfg.WARD_COL: "ward"})), use_container_width=True)


def _model_table(selection: dict) -> pd.DataFrame:
    chosen = selection["chosen"]["name"]
    table = pd.DataFrame(selection["candidates"])
    return table.assign(model=table["model"].where(table["model"] != chosen, table["model"] + "  ← chosen"))


def _holdout_table(holdout: dict) -> pd.DataFrame:
    rows = [{"model": "Moshari", **holdout["model"]}]
    rows += [{"model": name, **errors} for name, errors in holdout["baselines"].items()]
    return pd.DataFrame(rows)


def _fold_errors(meta: dict, selection: dict, horizon: int) -> pd.DataFrame:
    chosen = pd.DataFrame(selection["per_fold"]).assign(model="Moshari")
    baselines = pd.DataFrame(meta["backtest_baselines"]["per_fold"])
    baselines = baselines[baselines["horizon"] == horizon]
    return pd.concat([chosen[["fold", "model", "rmse"]], baselines[["fold", "model", "rmse"]]], ignore_index=True)


def validation_tab(meta: dict, ward: str, horizon: int) -> None:
    selection = meta["model_selection"]["horizons"][str(horizon)]
    holdout = meta["holdout"][str(horizon)]
    st.plotly_chart(split_timeline(meta["split"]), use_container_width=True)
    backtest, final = st.columns(2)
    backtest.markdown(f"#### Backtest · mean of 4 folds · {horizon} weeks ahead")
    backtest.dataframe(_model_table(selection), hide_index=True, use_container_width=True)
    final.markdown("#### Holdout · touched once")
    final.dataframe(_holdout_table(holdout), hide_index=True, use_container_width=True)
    final.caption("Beats both baselines on the holdout." if holdout["beats_baselines"] else "Does not beat both baselines.")
    st.plotly_chart(fold_error_chart(_fold_errors(meta, selection, horizon)), use_container_width=True)
    tiers = holdout["tiers"]
    recall, precision, coverage, coverage_nz, lag_gain = st.columns(5)
    recall.metric("Alert recall (holdout)", f"{tiers['alert_recall']:.0%}")
    precision.metric("Alert precision (holdout)", f"{tiers['alert_precision']:.0%}")
    coverage.metric("80% range coverage", f"{holdout['coverage_80']:.0%}")
    coverage_nz.metric("…on weeks with cases", f"{holdout['coverage_80_nonzero_weeks']:.0%}")
    lag_gain.metric("Lagged rain lowers RMSE by", f"{selection['lag_ablation']['lag_gain_pct']:.1f}%")
    left, right = st.columns(2)
    left.plotly_chart(confusion_chart(tiers["confusion_matrix"]), use_container_width=True)
    right.plotly_chart(lag_chart(meta["lag_correlation"]), use_container_width=True)
    series = meta["test_series"][str(horizon)]
    left, right = st.columns(2)
    left.plotly_chart(holdout_series_chart(series["dates"], series["wards"][ward], ward), use_container_width=True)
    right.plotly_chart(importance_chart(selection["group_importance"]), use_container_width=True)


def about_tab(meta: dict) -> None:
    info = meta["model_info"]
    st.markdown(
        f"""
### How Moshari works
- **Rain first, cases later.** Rain fills drains and containers; Aedes larvae become adults in 7–14 days,
  then infection and incubation follow. Our data shows the strongest rain–case link at a
  **{meta['lag_correlation']['peak_lag_deseasonalized']}-week lag**.
- **Same rain, different ward.** Each ward's drainage, crowding and sanitation are features and are
  multiplied with recent rain, so a waterlogged, crowded ward rises faster.
- **One model per horizon.** Separate models forecast 2, 3 and 4 weeks ahead, so errors do not compound.
- **Honest validation.** Four walk-forward folds plus a final holdout ({info['holdout_start']} → {info['holdout_end']}),
  always with a 4-week gap; never a random split.
- **Built for action.** Risk tiers come from training-data case quantiles; alerts are tuned to catch at
  least 70% of outbreak weeks on the backtest, and every forecast says why.

### Data
Organizer dataset (Google Sheet export): 60 wards × 522 weeks, {meta['split']['data_start']} → {meta['split']['data_end']}.
Weather, ward vulnerability scores and weekly dengue cases; see `docs/data_audit.md`.
"""
    )


def footer(meta: dict) -> None:
    info = meta["model_info"]
    st.markdown(
        f"<div class='m-footer'>0 API calls · 0 LLM tokens · model trained on {info['train_start']} → "
        f"{info['train_end']} · scikit-learn {info['sklearn_version']} · trained {info['trained_at'][:10]}</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Moshari · dengue early warning", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        bundle = get_bundle()
        meta = get_meta()
        weekly = get_weekly()
        frame = get_frame(bundle, bundle["trained_at"])
    except (ForecastError, OSError, ValueError) as exc:
        st.error(f"Moshari cannot start: {exc}")
        st.stop()
    ward, date, horizon, multiplier = sidebar(frame, weekly)
    header(date, horizon)
    forecast, priority, validation, about = st.tabs(["Forecast", "Priority list", "Validation", "About"])
    with forecast:
        _safe(lambda: forecast_tab(frame, bundle, weekly, ward, date, horizon, multiplier))
    with priority:
        _safe(lambda: priority_tab(frame, bundle, date, horizon))
    with validation:
        _safe(lambda: validation_tab(meta, ward, horizon))
    with about:
        _safe(lambda: about_tab(meta))
    footer(meta)


main()
