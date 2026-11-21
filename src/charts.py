"""Plotly figures for the dashboard. Pure functions: data in, figure out.

Tier colours are colour-blind safe (blue -> yellow -> orange -> dark red, rising luminance contrast)
and every chart that shows a tier also shows its name.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.explain import GROUP_LABELS
from src.tiers import TIERS

TIER_COLORS = {"Low": "#2C7BB6", "Medium": "#FFD966", "High": "#F28E2B", "Critical": "#B2182B"}
TIER_TEXT_COLORS = {"Low": "#FFFFFF", "Medium": "#1F2A30", "High": "#1F2A30", "Critical": "#FFFFFF"}
INK = "#1F2A30"
MUTED = "#6B7780"
RAIN = "#8FB3D1"
RAISES = "#B2182B"
LOWERS = "#2C7BB6"
TEAL = "#0F5257"
BREEDING_FILL = "rgba(242, 142, 43, 0.16)"
HALF_WEEK = pd.Timedelta(days=3.5)


def _style(fig: go.Figure, title: str, height: int = 360) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0, "font": {"size": 15, "family": "Georgia, serif"}},
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, Helvetica, Arial, sans-serif", "color": INK, "size": 12},
        margin={"l": 10, "r": 10, "t": 48, "b": 10},
        legend={"orientation": "h", "y": -0.18, "x": 0},
    )
    fig.update_xaxes(showgrid=False, linecolor="#D9D2C5")
    fig.update_yaxes(gridcolor="#ECE6DA", zerolinecolor="#D9D2C5")
    return fig


def driver_chart(impacts: dict) -> go.Figure:
    """Signed bars: how many cases each factor adds (red) or removes (blue) vs a typical week."""
    items = sorted(impacts.items(), key=lambda kv: kv[1])
    labels = [GROUP_LABELS[g] for g, _ in items]
    values = [v for _, v in items]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=[RAISES if v > 0 else LOWERS for v in values],
            text=[f"{v:+.1f}" for v in values],
            textposition="outside",
            hovertemplate="%{y}: %{x:+.2f} cases<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_color=MUTED, line_width=1)
    fig.update_xaxes(title="cases added (+) or removed (−) vs a typical week")
    return _style(fig, "Why: what moves this forecast", height=320)


def rain_cases_chart(history: pd.DataFrame, origin, target, forecast: dict) -> go.Figure:
    """Weekly rain bars + cases line, the 2-4 week breeding window before the target week, and the forecast."""
    origin, target = pd.Timestamp(origin), pd.Timestamp(target)
    past = history[history["date"] <= origin]
    after = history[history["date"] >= origin]
    fig = go.Figure()
    fig.add_bar(x=history["date"], y=history["rain"], name="rain (mm/week)", marker_color=RAIN, yaxis="y")
    fig.add_scatter(x=past["date"], y=past["cases"], name="cases", line={"color": INK, "width": 2}, yaxis="y2")
    fig.add_scatter(
        x=after["date"], y=after["cases"], name="cases that followed (hindsight)",
        line={"color": INK, "width": 1.5, "dash": "dot"}, yaxis="y2",
    )
    fig.add_scatter(
        x=[target], y=[forecast["predicted_cases"]], name="forecast (80% range)", mode="markers",
        marker={"color": TIER_COLORS[forecast["tier"]], "size": 13, "line": {"color": INK, "width": 1}},
        error_y={
            "type": "data", "symmetric": False, "color": INK,
            "array": [forecast["high_80"] - forecast["predicted_cases"]],
            "arrayminus": [forecast["predicted_cases"] - forecast["low_80"]],
        },
        yaxis="y2",
    )
    fig.add_vrect(
        x0=target - pd.Timedelta(weeks=4) - HALF_WEEK, x1=target - pd.Timedelta(weeks=2) + HALF_WEEK,
        fillcolor=BREEDING_FILL, line_width=0, annotation_text="breeding window", annotation_position="top left",
    )
    fig.add_vline(x=origin, line_dash="dash", line_color=MUTED)
    fig.update_layout(
        yaxis={"title": "rain (mm)", "showgrid": False},
        yaxis2={"title": "cases", "overlaying": "y", "side": "right", "rangemode": "tozero"},
    )
    return _style(fig, "Rain drives cases 2–4 weeks later", height=380)


def tier_heatmap(grid: pd.DataFrame) -> go.Figure:
    """Ward x horizon grid in the row order given. `grid` columns: ward, horizon, predicted_cases, tier."""
    order = list(dict.fromkeys(grid["ward"]))
    tiers = grid.pivot(index="ward", columns="horizon", values="tier").loc[order]
    cases = grid.pivot(index="ward", columns="horizon", values="predicted_cases").loc[order]
    z = tiers.apply(lambda col: col.map(TIERS.index))
    colors = [TIER_COLORS[t] for t in TIERS]
    scale = [[0, colors[0]], [1 / 6, colors[0]], [1 / 6, colors[1]], [0.5, colors[1]],
             [0.5, colors[2]], [5 / 6, colors[2]], [5 / 6, colors[3]], [1, colors[3]]]
    text = tiers + "<br>" + cases.round(1).astype(str)
    fig = go.Figure(
        go.Heatmap(
            z=z.values, x=[f"{h} weeks" for h in z.columns], y=list(z.index), zmin=0, zmax=3,
            colorscale=scale, showscale=False, text=text.values, texttemplate="%{text}",
            textfont={"size": 10}, xgap=2, ygap=2,
            hovertemplate="%{y} · %{x}<br>%{text} cases<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    return _style(fig, "Every ward, every horizon", height=max(360, 26 * len(z) + 80))


def split_timeline(split: dict) -> go.Figure:
    """Walk-forward folds and the final holdout on a real-date axis."""
    rows = []
    for fold in split["folds"]:
        name = f"Fold {fold['fold']}"
        rows += [
            {"row": name, "phase": "train", "start": split["data_start"], "end": fold["train_end"]},
            {"row": name, "phase": "test", "start": fold["test_start"], "end": fold["test_end"]},
        ]
    rows += [
        {"row": "Holdout", "phase": "train", "start": split["data_start"], "end": split["holdout_train_end"]},
        {"row": "Holdout", "phase": "holdout (touched once)", "start": split["holdout_start"], "end": split["data_end"]},
    ]
    frame = pd.DataFrame(rows)
    fig = px.timeline(
        frame, x_start="start", x_end="end", y="row", color="phase",
        color_discrete_map={"train": "#C9D6DF", "test": TEAL, "holdout (touched once)": "#F28E2B"},
    )
    fig.update_yaxes(autorange="reversed", title=None)
    return _style(fig, "Chronological validation: train → 4-week gap → test", height=300)


def fold_error_chart(per_fold: pd.DataFrame) -> go.Figure:
    """Grouped bars of RMSE per fold. Columns: fold, model, rmse."""
    fig = px.bar(
        per_fold, x="fold", y="rmse", color="model", barmode="group",
        color_discrete_sequence=[TEAL, "#B9B2A6", "#8C857A"],
    )
    fig.update_xaxes(title="fold", tickmode="linear")
    fig.update_yaxes(title="RMSE (cases)")
    return _style(fig, "Backtest error per fold (lower is better)", height=340)


def lag_chart(lag: dict) -> go.Figure:
    fig = go.Figure()
    fig.add_vrect(x0=1.5, x1=4.5, fillcolor=BREEDING_FILL, line_width=0,
                  annotation_text="biology: 2–4 weeks", annotation_position="top left")
    fig.add_scatter(x=lag["lags"], y=lag["spearman_raw"], name="raw", mode="lines+markers", line={"color": MUTED})
    fig.add_scatter(
        x=lag["lags"], y=lag["spearman_deseasonalized"], name="season removed",
        mode="lines+markers", line={"color": TEAL, "width": 3},
    )
    fig.update_xaxes(title="rain k weeks before", tickmode="linear")
    fig.update_yaxes(title="Spearman correlation with cases")
    return _style(fig, f"The data peaks at a {lag['peak_lag_deseasonalized']}-week lag", height=340)


def confusion_chart(matrix: list[list[int]]) -> go.Figure:
    fig = go.Figure(
        go.Heatmap(
            z=matrix, x=list(TIERS), y=list(TIERS), colorscale=[[0, "#FBF8F3"], [1, TEAL]],
            showscale=False, texttemplate="%{z}", hovertemplate="true %{y} → predicted %{x}: %{z}<extra></extra>",
        )
    )
    fig.update_xaxes(title="predicted tier")
    fig.update_yaxes(title="true tier", autorange="reversed")
    return _style(fig, "Holdout tiers: true vs predicted", height=320)


def holdout_series_chart(dates: list[str], series: dict, ward: str) -> go.Figure:
    """Holdout actuals vs forecast with the 80% band for one ward."""
    fig = go.Figure()
    fig.add_scatter(x=dates, y=series["hi"], line={"width": 0}, showlegend=False, hoverinfo="skip")
    fig.add_scatter(
        x=dates, y=series["lo"], fill="tonexty", fillcolor="rgba(15, 82, 87, 0.15)",
        line={"width": 0}, name="80% range",
    )
    fig.add_scatter(x=dates, y=series["pred"], name="forecast", line={"color": TEAL, "width": 2})
    fig.add_scatter(x=dates, y=series["y_true"], name="actual", line={"color": INK, "width": 1.5, "dash": "dot"})
    fig.update_yaxes(title="cases", rangemode="tozero")
    return _style(fig, f"Holdout: forecast vs what happened · {ward}", height=340)


def importance_chart(importance: dict) -> go.Figure:
    items = sorted(importance.items(), key=lambda kv: kv[1])
    fig = go.Figure(
        go.Bar(
            x=[v for _, v in items], y=[GROUP_LABELS[g] for g, _ in items], orientation="h",
            marker_color=TEAL, hovertemplate="%{y}: +%{x:.2f} RMSE<extra></extra>",
        )
    )
    fig.update_xaxes(title="RMSE increase when the group is shuffled")
    return _style(fig, "What the model relies on (backtest)", height=300)
