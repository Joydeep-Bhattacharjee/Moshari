# Data Audit — Moshari dengue dataset

**Source:** organizer Google Sheet, exported as CSV to `data/raw/dengue.csv` (2.5 MB).
**Reproduce:** `python -m src.validate` (validation rules + quality report).
**Audit date:** 2026-11-21.

## 1. Shape and coverage

| Fact | Value |
|---|---|
| Rows × columns | 31,320 × 12 |
| Wards | 60 (`ward_id`, e.g. `CCC_Ward_01`) |
| Cities | Dhaka North 20 wards, Dhaka South 20, Chattogram 10, Gazipur 5, Narayanganj 5 |
| Date range | 2016-01-04 → 2025-12-29 (522 weeks) |
| Rows per ward | 522 for every ward (balanced panel) |
| Spacing | every gap is exactly 7 days; every date is a Monday |
| Missing values | none in any column |
| Duplicate (ward, date) | none |

## 2. Decisions (recorded in `src/config.py`)

| Item | Decision |
|---|---|
| Date column | `date` (ISO, Monday of the week) |
| Grain | one row per ward per week (`W-MON`); no aggregation needed |
| Target | `dengue_cases` |
| Target type | weekly count, integer ≥ 0 → Poisson-type loss |
| Horizons | 2, 3, 4 weeks ahead |

## 3. Columns vs the PRD data contract

| Column | Range in data | Note |
|---|---|---|
| `rainfall_mm` | 0 – 268.83 (median 8.37) | ≥ 0 ✔ |
| `avg_temp_c` | 15.74 – 37.51 | lowercase `c` (PRD wrote `avg_temp_C`) |
| `max_temp_c`, `min_temp_c` | 23.12 – 40.79 / 13.06 – 31.64 | **not in PRD** — available as extra features |
| `relative_humidity_pct` | 41.84 – 99.00 | 0–100 ✔ |
| `water_logging_risk_index` | 0.22 – 0.94 | static per ward |
| `population_density_sqkm` | 18,314 – 74,252 | static per ward, > 0 ✔ |
| `sanitation_score` | 0.25 – 0.88 | static per ward |
| `city` | 5 values | **not in PRD** |
| `dengue_cases` | 0 – 41, mean 2.64, 58.0% zeros | all integers ✔ |

All PRD validation rules pass (`src/validate.py`, `tests/test_validate.py`).

## 4. Ward vulnerability columns

All three never change within a ward, so they act as ward-level constants.
Direction, measured as the Spearman correlation between each column and the ward's mean weekly cases (60 wards):

| Column | Spearman | Reading |
|---|---|---|
| `water_logging_risk_index` | **+0.810** | higher = worse drainage = more cases |
| `population_density_sqkm` | +0.539 | denser = more cases |
| `sanitation_score` | **−0.416** | higher = **better** sanitation = fewer cases |

→ Monotonic constraints are justified: +1 on waterlogging, −1 on sanitation (PRD §6.5).

## 5. Rain-lag evidence (preliminary, PRD §6.3)

Pooled Spearman correlation between `rainfall_mm` k weeks ago and `dengue_cases` this week (all ward-weeks).
"Season removed" subtracts each ward's average for that ISO week from both rain and cases, so the monsoon cycle alone cannot create the correlation.

| Lag k (weeks) | Raw | Season removed |
|---|---|---|
| 0 | 0.649 | 0.049 |
| 1 | 0.706 | 0.045 |
| 2 | 0.775 | 0.179 |
| **3** | **0.791** | **0.332** |
| 4 | 0.744 | 0.209 |
| 5 | 0.669 | 0.035 |
| 6 | 0.621 | −0.004 |
| 7 | 0.575 | 0.018 |
| 8 | 0.519 | −0.001 |

**Finding:** the peak is at **3 weeks** in both views, inside the biological 2–4 week window.
The season-removed curve is near zero outside lags 2–4, so the lag effect is not just seasonality.
Part 3.4 will compute this in `src/` and store it in `models/meta.json`.

## 6. Target distribution and tiers

- 58% of ward-weeks have zero cases → zero-heavy count target.
- Quantiles of positive weeks, full dataset: P50 = 5, P75 = 9, P90 = 14, P99 = 23.
- The final tier thresholds will be recomputed on the **training period only** (PRD §6.6); these full-data values are for orientation.
- Yearly totals vary from 6,530 (2021) to 10,013 (2022) with no steady upward or downward trend.

## 7. Caveats

- Data ends 2025-12-29. The PRD's CLI example date `2026-08-03` is outside the data.
- For h = 4, the last forecast-origin week with a known actual is 2025-12-01.
- The ward columns are constant, so the model cannot learn how a ward changes over time — only differences between wards.

## 8. Onsite dataset (Phase 2)

**Source:** organizer file `bangladesh_dengue_large_dataset_onsite.xlsx` (md5 `f0ca5b3294a9918922b096b774b34fbe`), exported by Google Sheets to CSV and committed as `data/raw/bangladesh_dengue_large_dataset_onsite.csv` (md5 `919cf51e5bf4403c0297f10640be21c3`).
**Reproduce:** `pytest tests/test_onsite_dataset.py`.
**Audit date:** 2026-11-27.

| Check | Result |
|---|---|
| CSV vs xlsx | header equal; all 31,320 × 15 cells equal (dates compared as Excel serials); the xlsx holds static values, no formulas |
| Shape | 31,320 × 15 — the 12 Phase 1 columns plus `saline_bags_needed`, `diagnostic_kits_needed`, `hospital_beds_required` |
| Phase 1 columns | byte-identical to `data/raw/dengue.csv`, same row order → the Phase 1 model and its holdout metrics stay valid, no retrain |
| Supply columns | integers ≥ 0, no missing values; all three are 0 on every zero-case row |

**Supply formulas.** Each supply column is a fixed multiple of `dengue_cases`, rounded to an integer.
Checked on all 31,320 rows (13,144 with cases > 0) with exact decimal arithmetic, so float error cannot hide a mismatch:

| Column | Per case | Exact `.5` ties in data | Mismatches: half-up | half-down | half-even |
|---|---|---|---|---|---|
| `saline_bags_needed` | 2.385 | 0 | 0 | 0 | 0 |
| `diagnostic_kits_needed` | 1.165 | 0 | 0 | 0 | 0 |
| `hospital_beds_required` | 0.300 | 1,197 | 1,197 | **0** | 969 |

**Finding:** ties are rounded **down** (5 cases → 1.5 → 1 bed; 15 → 4.5 → 4).
Only the beds column ever hits an exact `.5`, at 5, 15, 25 and 35 cases.
This differs from the PRD, which says round half up. The data is the ground truth, so Phase 2 rounds half down for all three columns, which matches every row.
The multipliers are stored as exact integers per 1,000 cases in `src/config.py` (`SUPPLY_PER_1000_CASES`), so Python and the TypeScript port compute identical integers with no float rounding.
