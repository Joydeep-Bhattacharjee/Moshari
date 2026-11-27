# Moshari — ward-level dengue early warning

[![CI](https://github.com/Joydeep-Bhattacharjee/Moshari/actions/workflows/ci.yml/badge.svg)](https://github.com/Joydeep-Bhattacharjee/Moshari/actions/workflows/ci.yml)

**Dengue follows rain by 2–4 weeks and hits wards differently. Moshari forecasts every ward's risk 2, 3 and 4 weeks ahead, says why, and ranks where spray teams should go first — before the peak, not after.**

- 60 wards (Dhaka North, Dhaka South, Chattogram, Gazipur, Narayanganj), weekly data 2016-01-04 → 2025-12-29
- Bilingual dashboard (English / বাংলা) that runs fully offline: **0 API calls, 0 LLM tokens**
- **Phase 2 (onsite final):** an Operations app that turns the forecasts into decisions under scarcity: saline, test kits and beds per ward, same-city patient transfers, spray-crew plans and the SMS / WhatsApp / A4 brief each ward receives. It opens at the site root; the Phase 1 forecast dashboard is at `#/forecast`. See [Phase 2](#phase-2-operations-forecast-to-action).
- Live demo: **https://moshari-dengue.vercel.app** (the same model output, served as static files)
- Video demo: **[watch on Google Drive](https://drive.google.com/drive/folders/1V1-U3qzLveCOFwAUWgBHRW8pvtZ-rPt-)**

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

## Quickstart — the dashboard (Node.js 22 or newer)

`npm run dev` first runs the trained model (`models/model.joblib`) through `python -m src.export` to rebuild every forecast the dashboard shows, when the Python environment below is set up. With Node.js alone it says so and uses the committed snapshot of that same model output, so the dashboard always starts.

```bash
git clone https://github.com/Joydeep-Bhattacharjee/Moshari.git
cd Moshari
npm ci
npm run dev
```

Open **http://127.0.0.1:8443** for the Phase 2 Operations app, or **http://127.0.0.1:8443/#/forecast** for the Phase 1 forecast dashboard. It works the same in PowerShell, macOS and Linux.

The latest week in the data (29 Dec 2025) is dry season, so every ward is Low. Pick a monsoon week (June–October, e.g. 4 Aug 2025) in the sidebar to see alerts.

## What the dashboard shows

| Tab | For the health officer |
|---|---|
| **Forecast** | Risk tier, predicted cases with the 80% range, what actually happened (when known), a 26-week rain-and-cases timeline with the breeding window, the factors driving the forecast with a plain-language reason, a what-if rainfall slider (0.5×–2× rain in the last 4 weeks), and the ward's drainage, density and sanitation scores |
| **Priority list** | All 60 wards ranked Critical first, tier counts, the real top driver per ward, a ward × horizon heatmap and a **CSV spray-team plan** download |
| **Validation** | The chronological split with real dates, holdout alert recall/precision, interval coverage, error per walk-forward fold, model vs both baselines, the lag-correlation chart, the alert confusion matrix, and forecast vs actual for the chosen ward |
| **About** | How it works, training dates, "0 API calls · 0 LLM tokens" |

Every number on screen comes from the trained model through `public/data/*.json`; nothing is simulated.

## Phase 2: Operations (forecast to action)

One scenario (as-of week, 1–4 week window, likely or bad-case P90 planning, stock and equity-floor sliders, crew pool and plan, crew effectiveness) drives the whole chain, recomputed in the browser in about 30 ms per change. Defaults show the 2025 peak (as-of 2025-06-30).

| Screen | For the operations officer |
|---|---|
| **Command overview** | Region alert banner, cases (likely and P90), critical wards, saline and kit shortfalls, unplaced patients, forecast vs actual, and all 60 wards in priority order |
| **Allocation** | Saline and test kits under scarce stock: equity floor first, then by priority; fill per ward, deficits and alerts |
| **Surge & routing** | Beds needed vs capacity per city, patient transfers within the city, transfer matrix, and saturated-city escalation |
| **What-if** | Spray crews lower water-logging and the forecast model shows the cases prevented, saline and kits avoided, the ROI leaderboard and the recommended deployment |
| **Dispatch** | Each ward's SMS (GSM length and segments), WhatsApp message and printable A4 brief, plus "Generate all 60" as a zip |
| **System** | Offline status, data hash and code commit, the scenario id, every parameter, and where we differ from the PRD |

Click any ward for **Explain this number**: the forecast and its driver, the risk cut-offs, the priority formula with its inputs, the supply formulas week by week, the floor and top-up, the crew effect and the bed position.

| Phase 2 step | Command (`make` target) |
|---|---|
| Dashboard data (also runs before `npm run dev`) | `python -m src.ops.ui_export` |
| Commissioner export pack (`exports/`) | `python -m src.ops.export_pack` (`make exports`) |
| Offline check: rebuild the pack with sockets blocked, then print the banner | `make offline-check` |
| Python → TypeScript golden fixtures | `python -m src.ops.parity` |

How it works, the formula sheet, the optimality arguments and the deviations from the PRD: [ARCHITECTURE.md](ARCHITECTURE.md#phase-2--forecast-to-action-dengueops).

## Python: retrain, re-export, weekly report (Python 3.12)

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt        # Windows: .venv\Scripts\python ...
```

With `.venv` in place, every `npm run dev` rebuilds the forecasts from `models/model.joblib` before the dashboard starts (about 10–25 s). If your environment lives elsewhere, point `MOSHARI_PYTHON` at its Python.

| Step | Command (`make` target) | Time |
|---|---|---|
| Validate the raw CSV | `python -m src.validate` (`make validate`) | ~2 s |
| Lag-correlation evidence | `python -m src.eda` (`make eda`) | ~3 s |
| Baseline backtest | `python -m src.backtest` (`make backtest`) | ~12 s |
| Model selection on 4 walk-forward folds | `python -m src.selection` (`make selection`) | ~3 min |
| Final fit + one holdout evaluation + bundle | `python -m src.train` (`make train`) | ~20 s |
| **Export forecasts for the dashboard** (also runs before `npm run dev`) | `python -m src.export` (`make export`) | ~10–25 s |
| Weekly spray-team CSV | `python -m src.report --date 2025-08-04 --horizon 3` (`make report`) | ~3 s |
| Tests | `python -m pytest -q` and `npm test` (`make test`) | ~3 min |

After retraining, always run `python -m src.export`, or the dashboard keeps showing the old forecasts (a test checks this).

## Repository map

```
index.html, src/App.tsx, src/components/   React dashboard (Vite + Tailwind + Plotly)
src/data.ts                                reads public/data/*.json; tiers, drivers, scenario lookup
public/data/                               dashboard.json + validation.json, written by src/export.py
src/validate.py  data contract checks       src/selection.py  model selection (backtest only)
src/data.py      weekly grid, gap fill      src/train.py      final fit, holdout, model bundle
src/features.py  leak-free lag features     src/predict.py    vectorized all-ward forecasts
src/split.py     holdout + folds            src/explain.py    drivers, permutation importance
src/baselines.py ward mean, seasonal naive  src/scenario.py   what-if rainfall
src/backtest.py  per-fold MAE/RMSE          src/export.py     JSON for the dashboard
src/models.py, src/tiers.py                 src/report.py     CSV spray-team plan
models/          model.joblib (2.4 MB), meta.json
src/ops/         Phase 2 decision core (Python): forecast window, demand, allocation, routing,
                 simulator, notices, export pack, offline self-check, fallback chain
src/lib/ops/     the same core in TypeScript for the browser;  src/ops-ui/  the Operations screens
public/data/ops/ config.json + forecasts.json, written by src/ops/ui_export.py
exports/         committed commissioner pack (golden files for the offline test)
tests/           313 Python tests;  scripts/test-dashboard.mjs + test-ops.test.ts  20 frontend tests
docs/            PRD, data audit
```

## External APIs and data

- **At runtime: none.** No weather API, no LLM, no web fonts (Inter, DM Sans and Noto Sans Bengali are bundled through npm), and the dev server listens on 127.0.0.1 only.
- **Dataset:** the organizer's Google Sheet, exported once to `data/raw/dengue.csv`. See [docs/data_audit.md](docs/data_audit.md).
- **Onsite dataset (Phase 2):** the same data plus saline, test-kit and bed columns, in `data/raw/bangladesh_dengue_large_dataset_onsite.csv`, checked cell by cell against the Phase 1 data and the organizer's `.xlsx` ([data audit §8](docs/data_audit.md#8-onsite-dataset-phase-2)).

## AI disclosure

| Tool | Who | What for |
|---|---|---|
| Claude Code (Anthropic, Claude Opus 5.5) | Joydeep | Phase 1: data audit, Python pipeline, tests, the data link between the model and the dashboard, documentation drafts. Every change was reviewed and committed by a team member; all numbers come from code in this repo. Phase 2: the decision core, its TypeScript port, the Operations screens, tests and docs (details in [AI_DISCLOSURE.md](AI_DISCLOSURE.md)). |
| Figma Make | Apu | Generated the first version of the React dashboard (layout, components, bilingual text). |
| Claude, Gemini | Apu | Dashboard development |
| ChatGPT, Claude | Ridwan | Project skeleton and data validation |

No AI model is used inside the product: forecasts come from scikit-learn models trained on the dataset.

## Team

| Member | GitHub account | Role |
|---|---|---|
| Joydeep | Joydeep-Bhattacharjee | Data audit, feature pipeline, models and validation, data link to the dashboard, docs |
| Apu | mehA16 | React dashboard (bilingual UI) |
| Ridwan | shrabonmd2021-arch | Project skeleton and data validation |

## Limitations

See [MODEL_CARD.md](MODEL_CARD.md#limitations). In short: an alert aid, not a diagnosis; trained on data up to May 2024; ward vulnerability scores are fixed per ward; intervals are wide on zero-case weeks; the Bangla text should be reviewed by a native speaker before field use.

Phase 2 adds: bed capacity is a proxy and crew effectiveness an assumption, so the crew effect is model-based sensitivity, not a causal estimate; forecast error passes into decisions (the 2-week model over-forecasts the 2025 peak); and wards in a city peak together, so routing often has to escalate instead. See [ARCHITECTURE.md §14](ARCHITECTURE.md#14-phase-2-limitations).
