# Moshari — ward-level dengue early warning

[![CI](https://github.com/Joydeep-Bhattacharjee/Moshari/actions/workflows/ci.yml/badge.svg)](https://github.com/Joydeep-Bhattacharjee/Moshari/actions/workflows/ci.yml)

**Dengue follows rain by 2–4 weeks and hits wards differently. Moshari forecasts every ward's risk 2, 3 and 4 weeks ahead, says why, and ranks where spray teams should go first — before the peak, not after.**

- 60 wards (Dhaka North, Dhaka South, Chattogram, Gazipur, Narayanganj), weekly data 2016-01-04 → 2025-12-29
- Runs fully offline from a saved model: **0 API calls, 0 LLM tokens**
- Video demo (under 3 min, one take): **[watch on Google Drive](https://drive.google.com/drive/folders/1V1-U3qzLveCOFwAUWgBHRW8pvtZ-rPt-)**

## Results (final holdout, 2024-07-01 → 2025-12-29, scored once)

| Horizon | Model | RMSE | Seasonal-naive RMSE | Ward-mean RMSE | Alert recall / precision | 80% range coverage (all weeks / weeks with cases) |
|---|---|---|---|---|---|---|
| 2 weeks | Poisson GLM | **2.54** | 3.93 | 4.23 | 0.696 / 0.59 | 0.93 / 0.84 |
| 3 weeks | Poisson GLM | **2.71** | 3.91 | 4.21 | 0.661 / 0.55 | 0.93 / 0.83 |
| 4 weeks | Gradient boosting (log target, monotonic) | **2.59** | 3.88 | 4.14 | 0.818 / 0.41 | 0.94 / 0.87 |

- The model beats both baselines at every horizon on the 4-fold walk-forward backtest **and** on the holdout (RMSE 31–35% below seasonal-naive).
- The data itself shows the breeding lag: rain–case correlation peaks at **3 weeks**, raw (0.79) and with the seasonal cycle removed (0.33).
- An "alert" is a High or Critical forecast. Alert thresholds were tuned on the backtest to catch ≥ 70% of outbreak weeks; on the holdout this held at 4 weeks and fell just short at 2 and 3 weeks (reported, not re-tuned).
- Full numbers: [ARCHITECTURE.md](ARCHITECTURE.md), [MODEL_CARD.md](MODEL_CARD.md), `models/meta.json`.

## Quickstart (about 3 minutes, Python 3.12)

**Windows (PowerShell)**
```powershell
git clone https://github.com/Joydeep-Bhattacharjee/Moshari.git; cd Moshari
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

**macOS / Linux**
```bash
git clone https://github.com/Joydeep-Bhattacharjee/Moshari.git && cd Moshari
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

The trained model (`models/model.joblib`, 2.4 MB) and data are in the repo, so the app starts without training. Open http://localhost:8501.

## What the app shows

| Tab | For the health officer |
|---|---|
| **Forecast** | Risk tier (Low / Medium / High / Critical), predicted cases with 80% range, a one-line reason, a driver chart, rain vs cases with the breeding window shaded, and a what-if slider ("2× rain in the last 4 weeks") |
| **Priority list** | All 60 wards ranked Critical first, tier counts, a ward × horizon heatmap, and a **CSV spray-team plan** download |
| **Validation** | Split timeline with real dates, model vs baselines, per-fold errors, alert recall/precision, confusion matrix, interval coverage, lag-correlation chart, forecast vs actual for the chosen ward |
| **About** | How it works, data source, "0 API calls · 0 LLM tokens" |

Tip: the latest week in the data (29 Dec 2025) is dry season and every ward is Low. Slide the week back to a monsoon week (June–October) to see alerts.

## Weekly report (CLI)

What a health office would schedule every Monday:

```bash
python -m src.report --date 2025-08-04 --horizon 3 --out reports/
# -> reports/spray_plan_2025-08-04_h3.csv  (rank, ward, tier, predicted cases, 80% range, top driver)
```

Without `--date` it uses the latest week.

## Retrain from scratch

| Step | Command (`make` target) | Time |
|---|---|---|
| Validate the raw CSV | `python -m src.validate` (`make validate`) | ~2 s |
| Lag-correlation evidence | `python -m src.eda` (`make eda`) | ~3 s |
| Baseline backtest | `python -m src.backtest` (`make backtest`) | ~12 s |
| Model selection on 4 walk-forward folds | `python -m src.selection` (`make selection`) | ~3 min |
| Final fit + one holdout evaluation + bundle | `python -m src.train` (`make train`) | ~20 s |
| Tests | `python -m pytest -q` (`make test`) | ~40 s |

On Windows without `make`, run the `python -m ...` commands with `.venv\Scripts\python`. `python -m src.features` writes `data/processed/features.csv` for inspection (not committed; rebuilt in seconds).

## Repository map

```
app.py                  Streamlit dashboard
src/validate.py         data contract checks           src/selection.py  model selection (backtest only)
src/data.py             weekly grid, gap fill          src/train.py      final fit, holdout, model bundle
src/features.py         leak-free lag features         src/predict.py    vectorized all-ward forecasts
src/split.py            holdout + walk-forward folds   src/explain.py    drivers and permutation importance
src/baselines.py        ward mean, seasonal naive      src/scenario.py   what-if rainfall
src/backtest.py         per-fold MAE/RMSE              src/report.py     CSV spray-team plan
src/models.py, tiers.py candidates, risk tiers         src/charts.py     dashboard figures
tests/                  128 tests (pytest), run in CI on every push
docs/                   PRD, data audit
```

## External APIs and data

- **At runtime: none.** No weather API, no LLM, no telemetry (`gatherUsageStats = false`; the server address is pinned so Streamlit does not look up the machine's public IP).
- **Dataset:** the organizer's Google Sheet, exported once to `data/raw/dengue.csv`. See [docs/data_audit.md](docs/data_audit.md).

## AI disclosure

| Tool | Who | What for |
|---|---|---|
| Claude Code (Anthropic, Claude Opus 5.5) | Joydeep | Data audit, code, tests and documentation drafts. Every change was reviewed and committed by a team member; all numbers come from code in this repo. |
| Gemini (Google) | Apu | Help with the demo video and the dashboard frontend |
| Astra | Ridwan | Help with part of the data and feature work |

No AI model is used inside the product: forecasts come from scikit-learn models trained on the dataset.

## Team

| Member | Role |
|---|---|
| **Joydeep** | Lead · documentation · data and features · model and validation |
| **Apu** | Demo video · dashboard frontend |
| **Ridwan** | Data and features (part) |

## Limitations

See [MODEL_CARD.md](MODEL_CARD.md#limitations). In short: an alert aid, not a diagnosis; trained on data up to May 2024; ward vulnerability scores are fixed per ward; intervals are wide on zero-case weeks.
