"""Commissioner export pack (PRD 6.4 bulk "Generate all 60", 6.5 golden files).

Usage: python -m src.ops.export_pack [--out exports]

exports/
  scenario.json          settings, scenario_id, data hash, git commit, generated time, summary
  sms/<ward>.txt  whatsapp/<ward>.txt  briefs/<ward>.html
  dispatch_all.csv       one row per ward: every notice field and the SMS text
  allocation.csv  transfers.csv  cities.csv
  commissioner_pack.zip  everything above, byte-deterministic (fixed entry times, sorted)

scenario.json holds everything needed to rebuild the pack exactly, which is what the
offline test does with the network blocked.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config as cfg
from src.ops.allocate import region_summary
from src.ops.brief import render_brief
from src.ops.dispatch_text import render_sms, render_whatsapp, sms_segments
from src.ops.notices import Notice, build_notices
from src.ops.pipeline import ScenarioRun, load_context, run_scenario
from src.ops.scenario import Scenario

EXPORT_DIR = cfg.ROOT / "exports"
DEMO_SCENARIO = Scenario(stock_pct=60)  # 60% stock so deficits, alerts and escalation show
ZIP_NAME = "commissioner_pack.zip"
PACK_FILES = ("scenario.json", "dispatch_all.csv", "allocation.csv", "transfers.csv", "cities.csv", ZIP_NAME)
ZIP_TIME = (1980, 1, 1, 0, 0, 0)  # fixed entry time: same inputs give the same zip bytes
TIME_FORMAT = "%Y-%m-%d %H:%M"


def _pairs(pairs: tuple[tuple[str, int], ...]) -> str:
    return ";".join(f"{ward}:{count}" for ward, count in pairs)


def dispatch_row(n: Notice) -> dict:
    sms = render_sms(n)
    return {
        cfg.WARD_COL: n.ward_id,
        cfg.CITY_COL: n.city,
        "risk": n.risk,
        "cases_p50": n.cases_p50,
        "cases_p90": n.cases_p90,
        "saline_allocated": n.saline_allocated,
        "saline_required": n.saline_required,
        "kits_allocated": n.kits_allocated,
        "kits_required": n.kits_required,
        "beds_required": n.beds_required,
        "beds_capacity": n.beds_capacity,
        "crews": n.crews,
        "sends": _pairs(n.sends),
        "receives": _pairs(n.receives),
        "unplaced": n.unplaced,
        "deficit": n.deficit,
        "sms_segments": sms_segments(sms),
        "sms": sms,
        "asof": n.asof,
        "scenario_id": n.scenario_id,
        "generated_at": n.generated_at,
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_csv(path: Path, table: pd.DataFrame) -> None:
    _write_text(path, table.to_csv(index=False, lineterminator="\n", float_format="%.4f"))


def _scenario_meta(run: ScenarioRun, data_hash: str, git_commit: str, generated_at: str) -> dict:
    return {
        "scenario": asdict(run.scenario),
        "scenario_id": run.scenario_id,
        "data_hash": data_hash,
        "git_commit": git_commit,
        "generated_at": generated_at,
        "summary": region_summary(run.allocation),
        "cities": run.routing.cities.round(2).to_dict(orient="records"),
        "crews_assigned": int(run.crews.sum()),
    }


def _zip(out_dir: Path) -> None:
    files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.name != ZIP_NAME)
    with zipfile.ZipFile(out_dir / ZIP_NAME, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(out_dir).as_posix(), date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def write_pack(run: ScenarioRun, out_dir: Path, generated_at: str, *, data_hash: str, git_commit: str) -> None:
    """Write the full pack for one scenario run into out_dir."""
    out_dir = Path(out_dir)
    notices = build_notices(run, generated_at)
    for n in notices:
        _write_text(out_dir / "sms" / f"{n.ward_id}.txt", render_sms(n))
        _write_text(out_dir / "whatsapp" / f"{n.ward_id}.txt", render_whatsapp(n))
        _write_text(out_dir / "briefs" / f"{n.ward_id}.html", render_brief(n))
    _write_csv(out_dir / "dispatch_all.csv", pd.DataFrame([dispatch_row(n) for n in notices]))
    _write_csv(out_dir / "allocation.csv", run.allocation)
    _write_csv(out_dir / "transfers.csv", run.routing.transfers)
    _write_csv(out_dir / "cities.csv", run.routing.cities)
    meta = _scenario_meta(run, data_hash, git_commit, generated_at)
    _write_text(out_dir / "scenario.json", json.dumps(meta, indent=2, sort_keys=True) + "\n")
    _zip(out_dir)


def current_commit() -> str:
    """Short git commit of the working tree, or 'unknown' outside a git checkout."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True, cwd=cfg.ROOT
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return done.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the commissioner export pack.")
    parser.add_argument("--out", type=Path, default=EXPORT_DIR)
    args = parser.parse_args(argv)
    commit = current_commit()
    ctx = load_context(git_commit=commit)
    run = run_scenario(DEMO_SCENARIO, ctx)
    write_pack(run, args.out, datetime.now().strftime(TIME_FORMAT), data_hash=ctx.data_hash, git_commit=commit)
    print(f"wrote {args.out} for scenario {run.scenario_id} (commit {commit})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
