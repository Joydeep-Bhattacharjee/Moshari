# DengueRadar

## Run

The Figma preview runs the React dashboard. The requested independent Streamlit
frontend lives in `app.py`:

```sh
python -m pip install -r requirements.txt
streamlit run app.py
```

No credentials, network services, or model files are needed. Sample data is
deterministic and explicitly labeled synthetic. The frontend makes no API or LLM
calls. The React preview uses Google Fonts; Python dependencies require an initial
installation. Neither dashboard should guide actual interventions without validation.

## Connect teammates' artifacts

All three files must be present and compatible; otherwise the entire Python
dashboard automatically falls back to mock mode. File modification signatures
invalidate the cached adapters on the next Streamlit rerun.

- `models/model.joblib`: trusted estimator/pipeline exposing `predict(DataFrame)`,
  returning one nonnegative case-count prediction per row. Use a multi-horizon
  estimator with `horizon` in its inputs. Only deserialize files you trust.
- `data/processed/features.csv`: one row per `ward_id,week` (unique), consistent
  timezone-naive weekly dates. Required columns: `ward_id`, `week`, `rainfall_mm`,
  `avg_temp_C`, `relative_humidity_pct`, `water_logging_risk_index`,
  `population_density_sqkm`, `sanitation_score`, plus the model's engineered
  numeric inputs. Optional `actual_cases` is the observed count **on that row's
  week**, not a future target. Never put future information in model inputs.
- `models/meta.json`: example below. Model input columns must be finite numeric
  columns; categorical preprocessing belongs in the saved pipeline and numeric
  feature contract. `horizon` is inserted by the adapter. Thresholds are case-count
  boundaries, not probabilities.

```json
{
  "feature_columns": ["rain_lag_2", "rain_lag_3", "rain_lag_4", "avg_temp_C", "relative_humidity_pct", "water_logging_risk_index", "population_density_sqkm", "sanitation_score", "horizon"],
  "trained_on": "2023-01-02 – 2024-12-30",
  "train_end": "2024-12-30",
  "validation_start": "2025-02-03",
  "tier_thresholds": [25, 50, 100],
  "interval_absolute_width": 14.2,
  "rainfall_scale_features": ["rain_lag_2", "rain_lag_3", "rain_lag_4"],
  "driver_groups": {
    "Rain Lags 2–4w": ["rain_lag_2", "rain_lag_3", "rain_lag_4"],
    "Temperature": ["avg_temp_C"],
    "Humidity": ["relative_humidity_pct"],
    "Ward Vulnerability": ["water_logging_risk_index", "population_density_sqkm", "sanitation_score"]
  }
}
```

`interval_absolute_width` should be an independently calibrated 80% residual
quantile. If absent, a clearly disclosed, **uncalibrated** 25% relative-width
fallback is used. Do not interpret that fallback as measured 80% coverage.

Rainfall scenarios require an explicit `rainfall_scale_features` list. Include
all lag/window/linear-interaction inputs that scale with rainfall. If engineering
nonlinear features, update `_predict` with the real feature-transform function;
do not simply scale nonlinear terms. Scenario controls are disabled if no
mapping exists. Drivers use grouped reference ablations against supplied
`reference_values` or dataset medians, **not SHAP or causal effects**; absent
groups show an attribution-unavailable notice.

Real validation is optional in `meta.json` under `validation`. Without it, no
mock scores are substituted into live mode. Expected keys:
`comparison` (records: Model, MAE, RMSE), `folds` (records: fold, MAE, RMSE),
`alert_recall`, `alert_precision`, `coverage` (fractions), `confusion_matrix`
(`[[TN,FP],[FN,TP]]`), `fit` (chronological held-out records: week, actual_cases,
pred_cases, lo, hi). These must come from genuine walk-forward predictions with
a four-week purge gap. Mock validation is illustrative; its fold summary and
ward-fit examples are independent synthetic demonstrations, not one experiment.

React's mock adapter is in `src/data.ts`; it does not load Python artifacts.
All four React tabs and EN/Bangla modes work locally. CSV exports reflect the
active week and horizon; rainfall scenarios intentionally do not change the
baseline spray-team ranking.
