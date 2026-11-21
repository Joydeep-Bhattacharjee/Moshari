
"""Project-wide dataset configuration."""

DATE_COLUMN = "date"
CITY_COLUMN = "city"
WARD_COLUMN = "ward_id"
TARGET_COLUMN = "dengue_cases"

DATA_GRAIN = "ward-week"
TARGET_TYPE = "count"

SANITATION_COLUMN = "sanitation_score"
SANITATION_DIRECTION = "higher_is_better"

RAW_DATA_PATH = "data/raw/dengue.csv"
