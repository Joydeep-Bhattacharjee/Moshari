# PRD v2 — Moshari: Ward-Level Dengue Early-Warning System

*Hackathon Prelim · 21–22 Nov 2026 · this file replaces `PRD_FINAL.md`. Exact code for the basics is in `AGENT_BUILD_SPEC.md`.*

**Hard deadline:** Sun 2:00 PM BST · **Our deadline:** 1:30 PM · **Feature freeze:** 10:30 AM

---

## 0. How winners think about this brief (read first)

1. **The judges score proof, not claims.** Every claim ("lags matter", "no leakage", "fast") needs a number, a test or a chart in the repo.
2. **40 of the 100 points are not ML** (setup, architecture doc, git history, disclosure), and **20 are the video**. Lock those down; don't spend 10 hours tuning.
3. **Use the problem's science in the model.** The brief gives you the biology (a 2–4 week breeding lag, plus drainage × crowding × sanitation). Encode it as features and constraints, then **prove it from the data** with a lag-correlation chart.
4. **Think like the end user.** A health officer needs "which wards, how sure, why, and what to do". Show alert recall and a ranked action list, not only RMSE.
5. **"Stage 1 of production":** modular `src/`, tests, CI, a CLI batch report and a model card. That signals the codebase is ready for the final round.

---

## 1. Problem (plain)

Rain fills drains and containers. Aedes eggs become adult mosquitoes in 7–14 days, then infection and incubation follow, so **hospital cases rise 2–4 weeks after rain**. Wards with poor drainage, high density and poor sanitation rise faster. Today the city sprays only after cases spike. **We predict each ward's risk 2–4 weeks ahead**, so spraying happens before the peak.

## 2. Goals & success metrics

| Goal | Metric | Target |
|---|---|---|
| Accurate forecasts | Test RMSE/MAE vs baselines | Beats the seasonal-naive **and** ward-mean baselines at h=2,3,4 |
| Catches outbreaks | **Alert recall** (true High/Critical weeks flagged High/Critical) | ≥ 0.70, reported with precision |
| Proves the lag | Rain-lag correlation peak + ablation | Peak inside 2–4 wks; lags improve RMSE by X% |
| Honest uncertainty | 80% interval coverage on test | 0.70–0.90 |
| Fast & cheap | App cold start / per-click latency | < 10 s / < 1 s, 0 API calls, 0 LLM tokens |
| Reproducible | Fresh clone → running app | ≤ 3 min |

## 3. Users & stories

| ID | As a health officer I want to… | Feature |
|---|---|---|
| S1 | see a ward's risk 2/3/4 weeks ahead | Forecast tab: tier + cases + 80% range |
| S2 | understand why | Driver chart + plain sentence |
| S3 | know where to send spray teams first | Priority list: all wards ranked, Critical first, CSV download |
| S4 | test "what if it rains heavily this week" | What-if rainfall slider (scenario) |
| S5 | trust the model | Validation tab: backtest MAE/RMSE per fold, alert recall, lag-proof chart |

## 4. Scope

**In:** CSV ingestion → validation → weekly per-ward features → walk-forward-validated models (h=2,3,4) → tiers + intervals + drivers → Streamlit dashboard + CLI report → tests + CI → docs → video.

**Out:** live weather APIs, auth, LLMs, deep learning, cloud deployment (optional only if all else is done).

## 5. Data contract (confirm in Part 2)

| Column | Meaning | Expected |
|---|---|---|
| `ward_id` | ward key | categorical |
| date col (TBD) | day/week | parseable date |
| `rainfall_mm` | rain | ≥ 0 |
| `avg_temp_C` | temperature | ~15–40 |
| `relative_humidity_pct` | humidity | 0–100 |
| `water_logging_risk_index` | poor drainage (↑ = worse, verify) | static per ward? |
| `population_density_sqkm` | people per km² | > 0 |
| `sanitation_score` | waste management (↑ = better?, **verify direction**) | static per ward? |
| target (TBD) | dengue cases / admissions | count ≥ 0 |

**Validation rules (`src/validate.py`; fail loudly):** required columns present; rain ≥ 0; humidity 0–100; temperature −5..50; no duplicate (ward, date); dates parse; ≥ 12 weeks per ward. Print a data-quality report.

---

## 6. ML design (the winning part)

### 6.1 Problem framing

- One row = **(ward, forecast-origin week t)**. Only information known at t is allowed.
- Predict **cases at t+h** for h ∈ {2,3,4}. One model per horizon (direct multi-horizon forecasting, so errors don't compound).
- Past case counts are **excluded** from the main model: the brief asks for weather-driven risk, and it keeps drivers meaningful. **Experiment E1** (optional) adds case lags and reports the gain in ARCHITECTURE.md as future work.

### 6.2 Features (all built with `groupby("ward_id")` after sorting)

| Group | Features | Why |
|---|---|---|
| Rain lags | `rain_lag_0..8` | the breeding clock |
| Rain windows | `rain_roll_2/4/6` (sum), `rain_sum_lag2_4`, `rain_max_4`, `heavy_rain_weeks_4` (count of weeks > ward P75 of train) | accumulation and extremes |
| Temperature | `temp_lag_0..3`, `temp_roll_4`, `temp_suitable_4` = weeks with 25 ≤ T ≤ 32 in the last 4 | Aedes thermal optimum |
| Humidity | `hum_lag_0..3`, `hum_roll_4` | mosquito survival |
| Ward vulnerability | `water_logging_risk_index`, `population_density_sqkm` (log1p), `sanitation_score` | hyper-local risk |
| Interactions | `rain2_4_x_waterlog`, `rain2_4_x_density`, `rain2_4_x_poor_sanitation` | "same rain, different ward" (straight from the brief) |
| Season | `week_sin`, `week_cos` | monsoon cycle without a 52-category jump |

Leakage guards: features use `shift(k ≥ 0)` only; the target uses `shift(-h)`; assert that no `y_*` column is in the features. Thresholds and medians are learned on train only.

### 6.3 Lag-proof analysis (EDA → evidence)

For k = 0..8, compute the Spearman correlation between `rain_lag_k` and cases, pooled over ward-weeks. **Expect the peak at k = 2–4.** Save to `meta.json` and show it as a chart in the app and the video ("the data itself shows a 3-week lag"). If the peak lands elsewhere, report it honestly and extend the lags.

### 6.4 Validation (judges care a lot)

- **Final holdout:** the last 15% of weeks, preceded by a 4-week purge gap, **touched once**.
- **Walk-forward backtest** on the remaining data: 4 expanding-window folds. Each fold trains on all weeks before its start, skips a 4-week gap, then tests on the next block. Report MAE/RMSE per fold and per horizon. This becomes the bonus "chronological validation error dashboard".
- Never random-split; never shuffle.

```
Fold1: [train.......] gap [test]
Fold2: [train...............] gap [test]
Fold3: [train.......................] gap [test]
Fold4: [train...............................] gap [test]
Holdout:                                       [train+val all] gap [HOLDOUT]
```

### 6.5 Models (pick by mean backtest RMSE)

| Model | Role |
|---|---|
| B1 ward mean | baseline |
| B2 seasonal naive (same ward, same ISO week last year; else ward mean) | strong baseline |
| M1 Poisson GLM (`PoissonRegressor` + scaling) | interpretable statistical model |
| **M2 HistGradientBoosting, `loss="poisson"`** | expected winner: count target, non-linear lag × vulnerability effects |
| M3 HGB `loss="squared_error"` on `log1p(y)` | alternative |

HGB settings: `max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=1.0, early_stopping=False, random_state=42`. **Monotonic constraints** (scientifically justified, robust, easy to explain): +1 on `rain_sum_lag2_4` and `water_logging_risk_index`; +1/−1 on `sanitation_score` **only after** Part 2 confirms its direction. Keep them only if the backtest RMSE doesn't worsen by more than 2%. Light tuning only: try 3 configs (learning rate 0.03/0.05/0.1) on the backtest. No grid searches.

### 6.6 Risk tiers

- Thresholds = train-target quantiles P50 / P75 / P90 → Low / Medium / High / Critical. Store them in the bundle; never recompute at inference.
- Zero-heavy data: compute on positive values; assert the thresholds are strictly increasing.
- **Tier metrics:** exact accuracy, within-one-tier accuracy, **alert recall & precision** (High+Critical), confusion matrix.
- **Threshold policy:** since missing an outbreak costs more than a false alarm, report the recall/precision trade-off and state the choice.

### 6.7 Uncertainty

HGB `loss="quantile"` at α = 0.1 and 0.9 per horizon. Clip so lo ≤ pred ≤ hi and all values ≥ 0. Report test coverage. Show it as a shaded band ("forecast confidence intervals" bonus).

### 6.8 Explainability (no SHAP dependency)

- **Local:** grouped ablation. Replace a feature group with train medians, re-predict, impact = change in cases. Show signed bars + the sentence "High risk in 3 weeks, mainly driven by heavy rain 2–4 weeks ago and poor drainage."
- **Global:** permutation importance by group on the backtest folds.

### 6.9 What-if scenario (S4)

A slider for "rainfall multiplier for the last 4 weeks" (0.5× to 2×). Recompute the affected rain features for that ward only (lags, rolls, interactions) and re-predict. Show the original vs scenario tier. This is cheap (one row) and makes a great demo moment.

### 6.10 Artifacts

- `models/model.joblib` (compress=3): `{models[h]: {point, q10, q90}, feature_cols, feature_groups, thresholds[h], train_medians, monotonic_cfg, sklearn_version, trained_at, data_hash}`
- `models/meta.json`: data audit, lag correlations, backtest table, holdout metrics, coverage, alert metrics, confusion matrices, group importance, test series (downsampled).
- `MODEL_CARD.md`: intended use, data, metrics, limitations, ethics (it is an alert aid, not a diagnosis).

---

## 7. App spec (Streamlit, `app.py`)

**Sidebar:** Ward · Forecast-origin week (valid dates only; default latest) · Horizon 2/3/4 · What-if rain multiplier.

**Tab 1 Forecast:** tier badge (colour + word) · predicted cases · 80% range · target week · actual (if known) · sentence · driver bar chart · rainfall bars + cases line (26 wks) with a shaded **2–4-week breeding window** · scenario comparison.

**Tab 2 Priority list:** all wards for the chosen week and horizon: tier, cases, range, top driver; Critical first; tier counts; **ward × horizon heatmap**; `st.download_button` CSV ("spray-team plan").

**Tab 3 Validation:** split timeline · baseline vs models table · backtest MAE/RMSE per fold chart · alert recall/precision + confusion matrix · coverage · lag-correlation chart · predicted vs actual with band for the selected ward.

**Tab 4 About:** how it works in 5 bullets · data source · "0 API calls · 0 LLM tokens · model trained on &lt;dates&gt;".

**Rules:** `@st.cache_resource` model, `@st.cache_data` features/meta; vectorized all-ward predict; `try/except` → `st.warning`, never a traceback; colour-blind-safe palette plus text labels.

**CLI** (production signal): `python -m src.report --date 2026-08-03 --horizon 3 --out reports/` writes the ranked CSV. This is what a health office would schedule weekly.

---

## 8. Engineering & repo

```
Moshari/
├─ README.md  ARCHITECTURE.md  MODEL_CARD.md  requirements.txt  Makefile  .gitignore
├─ .github/workflows/ci.yml        # pip install + pytest on push
├─ app.py
├─ data/raw/dengue.csv   data/processed/features.csv
├─ models/model.joblib   models/meta.json
├─ docs/data_audit.md    docs/PRD.md
├─ src/ config.py validate.py data.py features.py split.py baselines.py
│       train.py backtest.py predict.py explain.py scenario.py report.py
└─ tests/ test_features.py test_split.py test_predict.py test_validate.py
```

`Makefile`: `setup`, `features`, `train`, `test`, `app`. Also document the Windows equivalents in the README. Python 3.12; pinned: pandas, numpy, scikit-learn, joblib, streamlit, plotly, pytest.

---

## 9. PARTS (each = small commits by its owner)

Owners: **P1** Lead/Docs/Video · **P2** Data/Features · **P3** Model/Validation · **P4** App. With 3 people, P1 takes P4.

### PART 1 — Repo & environment · P1 · 9:30–10:00 PM

- [ ] 1.1 Public repo named `Moshari`, collaborators added, `.gitignore`, folders, `src/__init__.py`
- [ ] 1.2 Everyone sets `git config user.name/email` (GitHub email); disable the AI co-author line
- [ ] 1.3 venv + pinned `requirements.txt`; `Makefile`
- [ ] 1.4 CI workflow running pytest (green on the empty test). **Done when:** every member has pushed one commit. · `chore: skeleton, env, CI`

### PART 2 — Data audit & validation · P2 · 9:30–10:30 PM

- [ ] 2.1 CSV into `data/raw/`; print shape, dtypes, NaN %, wards, date range, rows per ward, duplicates
- [ ] 2.2 Decide the date column, target column, grain, target type → `config.py`, `docs/data_audit.md`
- [ ] 2.3 Check whether the ward columns are static per ward; **check the sanitation direction** (corr with cases)
- [ ] 2.4 `src/validate.py` + `tests/test_validate.py`. **Done when:** the audit is posted in the chat and P3 knows the target type. · `feat(data): audit + validation`

### PART 3 — Cleaning & features · P2 · 10:30 PM–1:00 AM · Rubric #2 (15)

- [ ] 3.1 `data.py`: weekly aggregation (rain sum, temp/hum mean, target sum), gap fill per ward, sort
- [ ] 3.2 `features.py`: all groups in §6.2, targets `y_h2..y_h4`, `FEATURE_GROUPS`
- [ ] 3.3 `tests/test_features.py`: 2-ward synthetic data → no cross-ward leakage, correct lag values, correct target shift, no `y_` columns in the features
- [ ] 3.4 Lag-correlation analysis (§6.3) → saved to `meta.json`, chart PNG for checking
- [ ] 3.5 `features.csv` written (keeps the latest weeks with NaN targets for live forecasts). **Done when:** tests pass and the lag-correlation peak is known. · `feat(features): per-ward lags`, `test(features)`, `feat(eda): lag correlation`

### PART 4 — Validation framework & baselines · P3 · 10:00 PM–12:30 AM

- [ ] 4.1 `split.py`: holdout + 4 walk-forward folds with 4-week gaps; `tests/test_split.py` (no overlap, gap ≥ 4)
- [ ] 4.2 `baselines.py`: ward mean, seasonal naive
- [ ] 4.3 `backtest.py`: a generic `run_backtest(model_factory, h)` → MAE/RMSE per fold. **Done when:** the baseline backtest table prints. · `feat(validation): walk-forward + baselines`

### PART 5 — Models & selection · P3 · 12:30–3:30 AM · Rubric #3 (15)

- [ ] 5.1 Backtest M1 Poisson GLM, M2 HGB-Poisson, M3 HGB-log for h=2,3,4
- [ ] 5.2 Monotonic-constraint variant; keep it if within 2%
- [ ] 5.3 3-config learning-rate check; pick the winner per horizon by mean backtest RMSE
- [ ] 5.4 **Lag ablation:** the winner without rain lags 1–8 → `lag_gain_pct`
- [ ] 5.5 Tier thresholds (train) + tier/alert metrics + confusion matrix
- [ ] 5.6 Quantile models + coverage
- [ ] 5.7 Refit on all pre-holdout data → **holdout once** → `meta.json`; save `model.joblib`
- [ ] 5.8 Permutation importance by group

**Done when:** the winner beats both baselines on the backtest and holdout; `python -m src.train` < 3 min. · `feat(model): ...` (3+ commits)

**If it doesn't beat the baselines:** check the shift signs and sort order, plot one ward's rain vs cases, try `log1p`, reduce the lags. Report honestly.

### PART 6 — Inference, drivers, scenario, CLI · P3 · 3:30–5:00 AM

- [ ] 6.1 `predict.py`: `predict_one`, `predict_all_wards` (vectorized), friendly errors
- [ ] 6.2 `explain.py`: grouped ablation + sentence
- [ ] 6.3 `scenario.py`: rain multiplier → rebuild the ward's rain features → re-predict
- [ ] 6.4 `report.py` CLI → CSV
- [ ] 6.5 `tests/test_predict.py`: loads the bundle, different inputs → different outputs, tiers valid, lo ≤ pred ≤ hi, scenario 2× rain ≥ 1× rain (monotonic). **Done when:** all tests pass. · `feat(predict)`, `feat(explain)`, `feat(scenario)`, `feat(cli)`

### PART 7 — Dashboard · P4 · 10:00 PM–8:00 AM · Rubric #4 (10) + bonus

- [ ] 7.1 Skeleton: 4 tabs, sidebar, caching (use a stub until 5:00 AM, then **delete the stub**)
- [ ] 7.2 Forecast tab (§7)
- [ ] 7.3 Driver chart + sentence
- [ ] 7.4 Rain/cases chart with breeding-window shading
- [ ] 7.5 What-if slider + comparison
- [ ] 7.6 Priority list + heatmap + CSV download
- [ ] 7.7 Validation tab (backtest folds, alert metrics, coverage, lag-correlation chart, pred vs actual band)
- [ ] 7.8 About tab + footer
- [ ] 7.9 Click 15 random combinations → zero errors, every click < 1 s. **Done when:** a teammate who hasn't seen it can explain a prediction from the screen alone. · 5+ commits

### PART 8 — Docs · P1 · 11:00 PM–10:00 AM · Rubric #1, #5, #6, #8

- [ ] 8.1 README: one-line pitch, quickstart (4 commands, Win + Mac/Linux), retrain, CLI, video link, screenshots, results table, team
- [ ] 8.2 README **AI disclosure** (every tool, who used it, for what) + **external APIs** (none at runtime; dataset = organizer Google Sheet)
- [ ] 8.3 ARCHITECTURE.md (1–2 pages): ① Mermaid data-flow diagram ② features + biology ③ **chronological split with real dates + walk-forward diagram + gap** ④ **model selection table with real numbers** + why HGB-Poisson + monotonic constraints ⑤ **cost controls**: 0 API calls, 0 LLM tokens, joblib size, `cache_resource` / `cache_data`, vectorized inference (measured ms), offline training; production plan: one batched weather pull per day, disk cache keyed by (date, location) with TTL, no per-ward API loops, any future LLM summary capped at a token budget and cached ⑥ limitations
- [ ] 8.4 MODEL_CARD.md; `docs/PRD.md` (sections 1–8 of this file). **Done when:** every rubric keyword appears in the docs with real numbers. · `docs: ...` (3+ commits)

### PART 9 — Freeze & verification · ALL · 10:30 AM–12:00 PM · Rubric #1, #8

- [ ] 9.1 Feature freeze; fixes only
- [ ] 9.2 **Fresh-clone test** on a different laptop (Windows if possible): clone → venv → install → `streamlit run app.py` → time it (≤ 3 min)
- [ ] 9.3 `pytest` green, CI badge green
- [ ] 9.4 `git log --format='%an %ad %s'`: all members, spread across the night, no AI author
- [ ] 9.5 The sklearn version in requirements = the bundle's version; no `.venv`; files < 50 MB
- [ ] 9.6 Every number in README/ARCHITECTURE = `meta.json`

### PART 10 — Video · P1 · 12:00–1:00 PM · Rubric #7 (20)

- [ ] 10.1 Clean screen, app on localhost, mic tested
- [ ] 10.2 Rehearse twice with a timer (≤ 2:45)
- [ ] 10.3 **One uncut take, no slides, voiceover**
- [ ] 10.4 Upload unlisted; link in the README; test in incognito

| Time | Show / say |
|---|---|
| 0:00 | "Dengue follows rain by 2–4 weeks and hits wards differently. Moshari warns officers before the peak." |
| 0:15 | Validation tab: lag-correlation chart — "our data peaks at a 3-week lag" |
| 0:35 | Forecast: pick a ward, the latest week, h=3 → tier, cases, range |
| 1:00 | Drivers + breeding-window chart — "heavy rain 3 weeks ago + poor drainage" |
| 1:20 | Change the horizon live; what-if 2× rain → tier rises |
| 1:45 | Priority list: Critical first, heatmap, CSV download |
| 2:05 | Backtest folds: beats the baselines, alert recall X, coverage Y |
| 2:30 | "Saved model, 0 API calls, 0 LLM tokens, runs locally in under 3 minutes." Stop by 2:50 |

### PART 11 — Submit · P1 · by 1:30 PM

- [ ] Tag `v1.0-prelim`, final push, submit the repo and video links, screenshot the confirmation

---

## 10. Timeline (from now)

| Time | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| 9:30–10:30 PM | Part 1 | Part 2 | read audit, start 4.1 | setup, 7.1 |
| 10:30 PM–1 AM | 8.1–8.2 draft | Part 3 | Part 4 | 7.2–7.4 (stub) |
| 1–3:30 AM | sleep | sleep | Part 5 | 7.5–7.6 |
| 3:30–5 AM | sleep | review tests | Part 6 | sleep |
| 5–8 AM | 8.3–8.4 | bug fixes, check numbers | sleep | real model wired, 7.7–7.9 |
| 8–10:30 AM | docs with real numbers | fresh-clone dry run | fixes | polish |
| 10:30 AM–12 PM | Part 9 | Part 9 | Part 9 | Part 9 |
| 12–1:30 PM | Parts 10–11 | check video | check video | check video |

## 11. Cut list (if behind, cut top first)

CI workflow → CLI report → monotonic constraints → what-if slider → MODEL_CARD → heatmap (keep the table) → walk-forward folds (keep the single train/val/holdout split). **Never cut:** feature tests, the trained joblib model, 4 tiers, the driver chart, README + disclosure, ARCHITECTURE.md, the fresh-clone test, the video, per-member commits.

## 12. Risk register

| Risk | Prevention |
|---|---|
| Cross-ward leakage | groupby + test 3.3 |
| Future leakage | shift rules, assert, purge gaps, train-only thresholds |
| Overfitting to the test set | holdout used once; selection on backtest only |
| Model ≤ baseline | troubleshooting in Part 5; honest reporting |
| Setup fails for the judges | pinned deps, committed model, fresh-clone test |
| Video disqualified | one take, ≤ 3:00, no slides |
| Git score 0 | per-task commits by every member |
| Sanitation sign wrong | verify in 2.3 before the monotonic constraint |
| Team burnout | sleep shifts in the timeline |

## 13. Definition of done

- [ ] Fresh clone runs in ≤ 3 min
- [ ] Per-ward multi-week lags + passing tests
- [ ] Trained model (joblib) beats the baselines; 4 tiers; live inference
- [ ] UI: inputs, tier, range, drivers, priority list, validation tab
- [ ] ARCHITECTURE.md: diagram, chronological split with dates, model rationale with numbers, cost controls
- [ ] README: quickstart, AI disclosure, external APIs, video link
- [ ] Video ≤ 3:00, uncut, voiceover, no slides
- [ ] Commits from every member across the 24 h
- [ ] Bonus: heatmap, intervals + coverage, backtest MAE/RMSE dashboard
