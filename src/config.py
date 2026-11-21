"""Project-wide constants: paths, data schema and validation limits.

Schema decisions are documented in docs/data_audit.md.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = ROOT / "data" / "raw" / "dengue.csv"
PROCESSED_DIR = ROOT / "data" / "processed"
FEATURES_PATH = PROCESSED_DIR / "features.csv"
FEATURE_PARAMS_PATH = PROCESSED_DIR / "feature_params.json"
MODELS_DIR = ROOT / "models"
META_PATH = MODELS_DIR / "meta.json"

# --- Schema -----------------------------------------------------------------
DATE_COL = "date"  # ISO date, Monday of each week
CITY_COL = "city"
WARD_COL = "ward_id"
TARGET_COL = "dengue_cases"  # weekly case count, integer >= 0

RAIN_COL = "rainfall_mm"
TEMP_COL = "avg_temp_c"
TEMP_MAX_COL = "max_temp_c"
TEMP_MIN_COL = "min_temp_c"
HUMIDITY_COL = "relative_humidity_pct"

DENSITY_COL = "population_density_sqkm"
WATERLOG_COL = "water_logging_risk_index"  # higher = worse drainage
SANITATION_COL = "sanitation_score"  # higher = better sanitation

STATIC_WARD_COLS = (DENSITY_COL, WATERLOG_COL, SANITATION_COL)
TEMP_COLS = (TEMP_COL, TEMP_MAX_COL, TEMP_MIN_COL)
WEATHER_COLS = (RAIN_COL, *TEMP_COLS, HUMIDITY_COL)
NUMERIC_COLS = (*STATIC_WARD_COLS, *WEATHER_COLS, TARGET_COL)
REQUIRED_COLS = (DATE_COL, CITY_COL, WARD_COL, *NUMERIC_COLS)

# --- Grain ------------------------------------------------------------------
DATA_FREQ = "W-MON"  # one row per ward per week; weeks start on Monday
HORIZONS = (2, 3, 4)  # forecast horizons in weeks

# --- Chronological split (PRD section 6.4) ----------------------------------
HOLDOUT_FRACTION = 0.15  # last 15% of weeks, touched once
PURGE_GAP_WEEKS = 4  # skipped weeks before each test block; must be >= max(HORIZONS)

# --- Validation limits (PRD section 5) --------------------------------------
# Inclusive (low, high) bounds; None means unbounded on that side.
RANGE_RULES = {
    RAIN_COL: (0.0, None),
    HUMIDITY_COL: (0.0, 100.0),
    TEMP_COL: (-5.0, 50.0),
    TEMP_MAX_COL: (-5.0, 50.0),
    TEMP_MIN_COL: (-5.0, 50.0),
    TARGET_COL: (0.0, None),
}
MIN_WEEKS_PER_WARD = 12
