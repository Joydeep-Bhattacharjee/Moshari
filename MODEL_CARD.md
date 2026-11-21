# Model card — Moshari dengue risk forecaster

## Intended use

- **Purpose:** forecast weekly dengue cases and a risk tier (Low / Medium / High / Critical) for each of 60 city wards, 2, 3 and 4 weeks ahead, so vector-control teams can spray before the peak.
- **Users:** city health officers planning mosquito control.
- **It is an alert aid, not a diagnosis.** It says where risk is likely to rise, never whether a person has dengue. Decisions stay with people who know the ground.
- **Out of scope:** individual patient care, hospital capacity planning, cities or wards not in the training data, forecasts beyond 4 weeks.

## Data

- **Source:** the organizer's Google Sheet, exported to `data/raw/dengue.csv`.
- **Coverage:** 31,320 rows, 60 wards × 522 weeks (Mondays 2016-01-04 → 2025-12-29), five cities. No missing values and no duplicates.
- **Columns:** weekly rainfall, average/min/max temperature, humidity; per-ward static population density, waterlogging index and sanitation score; weekly dengue case counts.
- **Target:** 0–41 cases per ward-week, 58% zeros.
- **Audit:** [docs/data_audit.md](docs/data_audit.md).

## Models (one per horizon)

| Horizon | Model | Settings |
|---|---|---|
| 2 weeks | Poisson GLM (median imputation, standard scaling) | alpha = 0.01 |
| 3 weeks | Poisson GLM | alpha = 0.01 |
| 4 weeks | Gradient boosting on log1p(cases) | learning rate 0.03, 400 iterations, monotonic: + recent rain, + waterlogging, − sanitation |
| 80% range (all horizons) | Gradient boosting, quantile loss α = 0.1 / 0.9 | same settings as the point model |

What-if scenarios (0.5×–2× rain in the last 4 weeks, in 0.25 steps) are precomputed with the same models for the dashboard.

Features: 34 per ward-week (rain lags and windows, temperature, humidity, ward vulnerability, rain × vulnerability, season). Past case counts are not used. The bundle stores the scikit-learn version (1.5.2), training time and a hash of the data file.

## Evaluation

Model choice used a 4-fold expanding walk-forward backtest (52-week test blocks, 4-week purge gaps). The final holdout (2024-07-01 → 2025-12-29) was scored once.

| Metric | 2 weeks | 3 weeks | 4 weeks |
|---|---|---|---|
| Backtest RMSE (model / seasonal naive) | 2.16 / 3.85 | 2.30 / 3.85 | 2.74 / 3.89 |
| Holdout RMSE (model / seasonal naive / ward mean) | 2.54 / 3.93 / 4.23 | 2.71 / 3.91 / 4.21 | 2.59 / 3.88 / 4.14 |
| Holdout MAE (model / seasonal naive) | 1.29 / 1.96 | 1.41 / 1.93 | 1.35 / 1.89 |
| Holdout exact tier / within one tier | 0.79 / 0.97 | 0.77 / 0.96 | 0.74 / 0.91 |
| Holdout alert recall / precision | 0.696 / 0.59 | 0.661 / 0.55 | 0.818 / 0.41 |
| Holdout 80% coverage: all weeks / weeks with cases | 0.93 / 0.84 | 0.93 / 0.83 | 0.94 / 0.87 |

- **Tier thresholds:** 5 / 9 / 14 cases, from training data.
- **Alert setting:** alerts are tuned on the backtest to catch ≥ 70% of outbreak weeks (decision scales 0.8 / 0.8 / 0.7).

## Limitations

- **Alert recall below target:** 0.66 at 3 weeks and 0.696 at 2 weeks on the holdout, against the 0.70 target. Some outbreak weeks will be missed; use the 80% range upper bound as a second signal.
- **Intervals too wide on zero-case weeks** (coverage 0.93–0.94 overall). Coverage on weeks with cases is in range.
- **Training data ends 2024-05-27.** Forecasts for 2025 come from a model that has not seen 2024–2025 seasons. Retrain before real use.
- **Static ward scores:** vulnerability scores do not change over time, so improvements in a ward's drainage would not show until the scores are updated.
- **Scenario at 4 weeks:** the 4-week model is only partly monotonic. In 1 of 120 checks, doubling recent rain lowered the forecast slightly (11.26 → 10.97 cases). The 2- and 3-week models behaved monotonically in every check.
- **One region, one dataset.** Do not transfer to other cities without retraining and validation.
- **Bangla text** in the dashboard was written for this project and should be reviewed by a native speaker before field use.

## Ethical considerations

- A "Critical" label can stigmatise a neighbourhood. Share ward rankings with health teams, not as public blame.
- False alarms cost spray-team time; missed outbreaks cost health. The alert setting favours recall, and that trade-off is shown in the app's Validation tab.
- No personal data is used. All data is aggregated weekly counts per ward.

## Maintenance

Retrain with `python -m src.selection` then `python -m src.train`, then refresh the dashboard data with `python -m src.export`. Check that the backtest still beats both baselines, and that `sklearn_version` in the bundle matches `requirements.txt`.
