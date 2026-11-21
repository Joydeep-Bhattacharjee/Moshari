
# Dengue Dataset — Data Audit Report

## 1. Dataset Overview

| Property | Value |
|---|---|
| Dataset file | dengue.csv |
| Total rows | 31,320 |
| Total columns | 12 |
| Unique wards | 60 |
| Unique cities | 5 |
| Date range | 2016-01-04 to 2025-12-29 |
| Unique observation dates | 522 |
| Data grain | Ward-week |
| Target column | dengue_cases |
| Target type | Non-negative integer count (regression) |

Each row represents one ward's observation for one week.

## 2. Column Information

| Column | Data type | Description |
|---|---|---|
| date | object | Observation date |
| city | object | City name |
| ward_id | object | Ward identifier |
| population_density_sqkm | int64 | Population density |
| water_logging_risk_index | float64 | Waterlogging risk |
| sanitation_score | float64 | Sanitation quality score |
| avg_temp_c | float64 | Average temperature |
| max_temp_c | float64 | Maximum temperature |
| min_temp_c | float64 | Minimum temperature |
| rainfall_mm | float64 | Rainfall |
| relative_humidity_pct | float64 | Relative humidity |
| dengue_cases | int64 | Weekly dengue case count |

Note: The date column is initially stored as an object/string and must be converted to datetime.

## 3. Missing Values

All 12 columns have zero missing values.

| Check | Result |
|---|---:|
| Total missing values | 0 |
| Missing percentage | 0% |

## 4. City and Ward Distribution

| City | Number of wards | Number of rows |
|---|---:|---:|
| Chattogram | 10 | 5,220 |
| Dhaka North | 20 | 10,440 |
| Dhaka South | 20 | 10,440 |
| Gazipur | 5 | 2,610 |
| Narayanganj | 5 | 2,610 |
| Total | 60 | 31,320 |

Every ward contains exactly 522 observations.

## 5. Date and Temporal Grain

- Earliest date: 2016-01-04
- Latest date: 2025-12-29
- Unique dates: 522
- Observations are spaced seven days apart.
- Each ward has one observation per date.

Therefore, the dataset has a ward-week grain.

## 6. Duplicate Checks

| Check | Result |
|---|---:|
| Duplicate complete rows | 0 |
| Duplicate date + ward combinations | 0 |

The date and ward combination uniquely identifies each observation.

## 7. Target Variable

Target: `dengue_cases`

| Statistic | Value |
|---|---:|
| Mean | 2.636 |
| Median | 0 |
| Minimum | 0 |
| Maximum | 41 |
| Standard deviation | 4.608 |

The target represents non-negative integer dengue case counts.

The prediction task is therefore count regression.

## 8. Ward-Level Static Features

The following columns have one unique value per ward throughout the dataset:

- city
- population_density_sqkm
- water_logging_risk_index
- sanitation_score

These features are static at the ward level in this dataset.

They should not be interpreted as weekly changing measurements.

## 9. Sanitation Direction Analysis

The dataset's sanitation score has the following confirmed interpretation:

Higher sanitation score = Better sanitation.

The observed correlations are:

| Analysis | Correlation with dengue cases |
|---|---:|
| Row-level sanitation score vs cases | -0.061 |
| Ward-level sanitation score vs mean cases | -0.400 |

The ward-level association is negative, suggesting that wards with better sanitation tend to have fewer dengue cases.

This is an observational association and does not establish causation.

## 10. Initial Audit Conclusions

1. The dataset contains 31,320 observations across 60 wards.
2. The observation grain is ward-week.
3. There are no missing values.
4. No duplicate rows or duplicate date-ward combinations were found.
5. The date column requires datetime conversion.
6. The target variable is dengue_cases, a non-negative count.
7. Sanitation score is static per ward and higher values indicate better sanitation.
8. Population density and waterlogging risk are also static per ward.

## 11. Validation Requirements

The validation module should check:

- Required columns exist.
- Date values are valid.
- Dengue cases are non-negative integers.
- No missing values exist in required fields.
- No duplicate date-ward combinations exist.
- Ward-level static features remain constant.
- Sanitation score follows the confirmed higher-is-better interpretation.
