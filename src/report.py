"""Weekly spray-team plan: every ward ranked by forecast risk, written to CSV (PRD section 7).

Usage: python -m src.report --date 2025-08-04 --horizon 3 --out reports/
Without --date the latest week in the data is used.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src import config as cfg
from src.predict import load_bundle, load_feature_frame, predict_all_wards, valid_dates

REPORT_COLUMNS = (
    "rank",
    cfg.WARD_COL,
    cfg.CITY_COL,
    "forecast_week",
    "target_week",
    "tier",
    "alert",
    "predicted_cases",
    "low_80",
    "high_80",
    "top_driver",
)


def build_report(frame: pd.DataFrame, bundle: dict, date, horizon: int) -> pd.DataFrame:
    table = predict_all_wards(frame, bundle, date, horizon)
    rounded = table.assign(
        **{col: table[col].round(1) for col in ("predicted_cases", "low_80", "high_80")},
        forecast_week=table["forecast_week"].dt.date,
        target_week=table["target_week"].dt.date,
    )
    return rounded[list(REPORT_COLUMNS)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the ranked ward risk report as CSV.")
    parser.add_argument("--date", help="forecast week (a Monday, YYYY-MM-DD); default: latest")
    parser.add_argument("--horizon", type=int, default=3, choices=cfg.HORIZONS)
    parser.add_argument("--out", type=Path, default=cfg.ROOT / "reports")
    args = parser.parse_args(argv)
    try:
        bundle = load_bundle()
        frame = load_feature_frame(bundle)
        date = pd.Timestamp(args.date) if args.date else valid_dates(frame)[-1]
        report = build_report(frame, bundle, date, args.horizon)
    except ValueError as exc:  # ForecastError and unparseable dates
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"spray_plan_{date.date()}_h{args.horizon}.csv"
    report.to_csv(path, index=False)
    print(f"wrote {path}: {len(report)} wards, tiers {report['tier'].value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
