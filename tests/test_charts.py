import pandas as pd
import plotly.graph_objects as go

from src.charts import (
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

FORECAST = {"predicted_cases": 6.0, "low_80": 2.0, "high_80": 11.0, "tier": "High"}


def test_driver_chart_colours_by_direction():
    fig = driver_chart({"rain": 2.5, "season": -1.0})
    bar = fig.data[0]
    assert list(bar.y) == ["season", "recent rain"]
    assert bar.marker.color[0] != bar.marker.color[1]


def test_rain_cases_chart_marks_forecast_with_interval():
    dates = pd.date_range("2025-06-02", periods=12, freq="W-MON")
    history = pd.DataFrame({"date": dates, "rain": range(12), "cases": range(12)})
    fig = rain_cases_chart(history, dates[8], dates[-1], FORECAST)
    forecast_trace = [t for t in fig.data if t.name == "forecast (80% range)"][0]
    assert list(forecast_trace.error_y.array) == [5.0]
    assert list(forecast_trace.error_y.arrayminus) == [4.0]
    assert len(fig.layout.shapes) == 2  # breeding window + forecast line


def test_heatmap_keeps_given_row_order():
    grid = pd.DataFrame(
        {
            "ward": ["Z", "Z", "A", "A"],
            "horizon": [2, 3, 2, 3],
            "predicted_cases": [9.0, 10.0, 1.0, 2.0],
            "tier": ["High", "High", "Low", "Low"],
        }
    )
    assert list(tier_heatmap(grid).data[0].y) == ["Z", "A"]


def test_validation_charts_build():
    split = {
        "data_start": "2016-01-04", "data_end": "2025-12-29",
        "holdout_train_end": "2024-05-27", "holdout_start": "2024-07-01",
        "folds": [{"fold": 1, "train_end": "2020-05-04", "test_start": "2020-06-08", "test_end": "2021-05-31"}],
    }
    lag = {"lags": [0, 1, 2, 3], "spearman_raw": [0.6, 0.7, 0.8, 0.79],
           "spearman_deseasonalized": [0.0, 0.1, 0.2, 0.33], "peak_lag_deseasonalized": 3}
    series = {"y_true": [1, 2], "pred": [1.5, 2.5], "lo": [0, 1], "hi": [3, 4]}
    figures = [
        split_timeline(split),
        fold_error_chart(pd.DataFrame({"fold": [1, 1], "model": ["Moshari", "B2"], "rmse": [2.0, 3.0]})),
        lag_chart(lag),
        confusion_chart([[5, 1, 0, 0], [1, 3, 1, 0], [0, 1, 2, 1], [0, 0, 1, 2]]),
        holdout_series_chart(["2025-01-06", "2025-01-13"], series, "W1"),
        importance_chart({"rain": 1.7, "season": 1.1}),
    ]
    assert all(isinstance(fig, go.Figure) and fig.data for fig in figures)
    assert "3-week lag" in figures[2].layout.title.text
