# PRD — Moshari: Ward-Level Dengue Early Warning

## 1. Problem

Rain fills drains and containers. Aedes eggs become adult mosquitoes in 7–14 days, then infection and incubation follow, so dengue cases rise 2–4 weeks after rain. Wards with poor drainage, high density and poor sanitation rise faster. City corporations spray after hospital cases spike, when transmission is already weeks ahead.

## 2. Goal

Forecast each ward's dengue risk 2, 3 and 4 weeks ahead from weather and ward vulnerability, so health officers can send spray teams before the peak.

## 3. Success metrics

| Metric | Target | Result (holdout 2024-07-01 → 2025-12-29) |
|---|---|---|
| RMSE vs seasonal-naive and ward-mean baselines | lower at h = 2, 3, 4 | 2.54 / 2.71 / 2.59 vs 3.93 / 3.91 / 3.88 (seasonal naive) |
| Alert recall (true High/Critical weeks flagged High/Critical) | ≥ 0.70 | 0.696 / 0.661 / 0.818 |
| 80% interval coverage | 0.70–0.90 | 0.93–0.94 all weeks; 0.83–0.87 on weeks with cases |
| Rain-lag peak | inside 2–4 weeks | 3 weeks |
| Fresh clone → running dashboard | ≤ 3 min | ~2 min |
| External API calls / LLM tokens at runtime | 0 / 0 | 0 / 0 |

## 4. Users and stories

| ID | As a health officer, I want to… | Feature |
|---|---|---|
| S1 | see a ward's risk 2/3/4 weeks ahead | risk tier, predicted cases, 80% range |
| S2 | understand why | driver chart and one-line reason |
| S3 | know where to send spray teams first | ranked priority list, CSV download |
| S4 | test "what if it rains more" | rainfall scenario slider (0.5×–2×) |
| S5 | trust the forecast | validation view: split, baselines, errors per fold, alert metrics |

## 5. Scope

**In:** CSV ingestion and validation, weekly per-ward features, chronologically validated models for h = 2, 3, 4, risk tiers, intervals, drivers, rainfall scenario, React dashboard, CLI report, tests, CI, documentation.

**Out:** live weather APIs, user accounts, LLMs, deep learning, cloud deployment.

## 6. Data

Source: organizer Google Sheet, exported to `data/raw/dengue.csv` — 31,320 rows, 60 wards × 522 weeks (Mondays 2016-01-04 → 2025-12-29), 5 cities.

| Column | Meaning |
|---|---|
| `date`, `ward_id`, `city` | week (Monday), ward key, city |
| `rainfall_mm`, `avg_temp_c`, `max_temp_c`, `min_temp_c`, `relative_humidity_pct` | weekly weather |
| `water_logging_risk_index`, `population_density_sqkm`, `sanitation_score` | ward vulnerability (constant per ward) |
| `dengue_cases` | weekly case count (target) |

**Validation rules** (`src/validate.py`, fail loudly): required columns, no missing values, numeric types, rain ≥ 0, humidity 0–100, temperature −5–50 °C, cases are non-negative integers, density > 0, no duplicate (ward, week), dates parse, ≥ 12 weeks per ward.

## 7. Functional requirements

| ID | Requirement |
|---|---|
| F1 | Ingest the raw CSV, validate it and build a complete weekly grid per ward |
| F2 | Compute multi-week rain lags (0–8 weeks), rain windows, temperature and humidity lags, ward vulnerability, rain × vulnerability interactions and season, grouped by `ward_id` with no future data |
| F3 | Train one model per horizon (2, 3, 4 weeks) and choose it on a walk-forward backtest |
| F4 | Output predicted cases, an 80% interval and a risk tier (Low / Medium / High / Critical) for any ward and week |
| F5 | Explain each forecast by feature group, with a plain-language sentence |
| F6 | Re-forecast a ward with its last 4 weeks of rain scaled 0.5×–2× |
| F7 | Rank all wards for a week and horizon; export the list as CSV |
| F8 | Show forecast, priority list, validation evidence and method in a bilingual (English / বাংলা) web dashboard |

## 8. Build steps

| Step | Output | Command |
|---|---|---|
| 1. Repository and environment | folders, pinned `requirements.txt`, `package.json`, Makefile, CI | `make setup` |
| 2. Data audit and validation | `docs/data_audit.md`, `src/validate.py` | `python -m src.validate` |
| 3. Weekly grid and features | `src/data.py`, `src/features.py` (34 features, targets `y_h2..y_h4`) | `python -m src.features` |
| 4. Lag evidence | rain-lag correlation, raw and season-removed, in `models/meta.json` | `python -m src.eda` |
| 5. Chronological split and baselines | holdout + 4 walk-forward folds with 4-week gaps; ward-mean and seasonal-naive baselines | `python -m src.backtest` |
| 6. Model selection | Poisson GLM vs gradient boosting (Poisson / log target), learning-rate check, monotonic constraints, lag ablation, alert threshold, feature-group importance | `python -m src.selection` |
| 7. Final training | fit on pre-holdout weeks, score the holdout once, save `models/model.joblib` | `python -m src.train` |
| 8. Inference | all-ward forecasts, drivers, rainfall scenario, CSV report | `python -m src.report` |
| 9. Dashboard data | every forecast the dashboard shows, from `model.joblib`, into `public/data/*.json` (also runs before `npm run dev`) | `python -m src.export` |
| 10. Dashboard | React app: Forecast, Priority list, Validation, About | `npm run dev` |
| 11. Tests and CI | Python tests and frontend data tests on every push | `make test` |
| 12. Documentation | `README.md`, `ARCHITECTURE.md`, `MODEL_CARD.md` | — |

## 9. Model design

- **Framing:** one row per (ward, forecast week *t*); predict cases at *t + h*. Separate models per horizon, so errors do not compound.
- **Leakage guards:** features use only weeks ≤ *t*; targets use `shift(-h)`; thresholds are learned on training weeks only.
- **Validation:** last 15% of weeks as the holdout, after a 4-week gap, scored once. Model choice uses 4 expanding walk-forward folds (52-week test blocks, 4-week gaps).
- **Selected models:** Poisson GLM for 2 and 3 weeks; gradient boosting on log cases with monotonic constraints (+ rain, + waterlogging, − sanitation) for 4 weeks.
- **Tiers:** P50 / P75 / P90 of positive training cases (5 / 9 / 14). Forecasts are tiered with a decision scale tuned for ≥ 0.70 backtest alert recall.
- **Uncertainty:** quantile models at 10% and 90%.
- **Explanations:** grouped ablation against training medians (local); grouped permutation importance (global).

## 10. Non-functional requirements

| Area | Requirement |
|---|---|
| Speed | dashboard click < 1 s (measured ~5 ms); 60-ward forecast < 1 s (measured ~150 ms) |
| Cost | 0 API calls, 0 LLM tokens at runtime; fonts bundled locally |
| Reproducibility | pinned dependencies; seeded models; same model and data give byte-identical exports |
| Security | dev server bound to 127.0.0.1; only trusted, committed `joblib` files are loaded |
| Usability | colour-blind-safe tiers with text labels; English, Bangla and bilingual modes |

## 11. Deliverables

- Public GitHub repository with distributed commits from all members
- `README.md`: quickstart, results, AI disclosure, external APIs
- `ARCHITECTURE.md`: data-flow diagram, chronological split, model selection, cost controls
- `MODEL_CARD.md`: intended use, metrics, limitations, ethics
- `models/model.joblib`, `models/meta.json`, `public/data/*.json`
- Uncut demo video (≤ 3 min) on localhost

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Cross-ward or future leakage | per-ward `groupby` shifts, purge gaps, train-only thresholds, leakage tests |
| Tuning to the holdout | holdout scored once; all choices made on the backtest |
| Model not better than baselines | both baselines reported per fold and on the holdout |
| Setup fails for judges | pinned dependencies, committed model and dashboard data, fresh-clone test |
| Stale dashboard numbers | export runs before every `npm run dev`; a test compares the exported data with `meta.json` |
