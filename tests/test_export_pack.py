"""Commissioner export pack (PRD 6.4 bulk export): files, CSV, deterministic zip."""
import json
import zipfile

import pandas as pd
import pytest

from src import config as cfg
from src.ops.export_pack import DEMO_SCENARIO, PACK_FILES, write_pack
from src.ops.pipeline import load_context, run_scenario

pytestmark = pytest.mark.skipif(
    not (cfg.MODEL_PATH.exists() and cfg.ONSITE_DATA_PATH.exists()),
    reason="trained model or onsite data not present",
)
GENERATED_AT = "2026-11-27 10:15"
PROVENANCE = {"data_hash": "datahash", "git_commit": "test"}


@pytest.fixture(scope="module")
def run():
    return run_scenario(DEMO_SCENARIO, load_context(git_commit="test"))


@pytest.fixture(scope="module")
def pack(run, tmp_path_factory):
    out = tmp_path_factory.mktemp("pack")
    write_pack(run, out, GENERATED_AT, **PROVENANCE)
    return out


def test_one_sms_whatsapp_and_brief_per_ward(pack):
    for folder, suffix in (("sms", ".txt"), ("whatsapp", ".txt"), ("briefs", ".html")):
        files = sorted((pack / folder).glob(f"*{suffix}"))
        assert len(files) == 60, folder
        assert files[0].name == f"CCC_Ward_01{suffix}"


def test_top_level_files_are_all_written(pack):
    for name in PACK_FILES:
        assert (pack / name).is_file(), name


def test_dispatch_csv_has_one_row_per_ward_with_the_sms(pack, run):
    table = pd.read_csv(pack / "dispatch_all.csv")
    assert len(table) == 60
    assert (table["scenario_id"] == run.scenario_id).all()
    first = table.set_index("ward_id").loc["CCC_Ward_01"]
    assert first["sms"] == (pack / "sms" / "CCC_Ward_01.txt").read_text(encoding="utf-8")


def test_scenario_json_records_how_to_reproduce_the_pack(pack, run):
    meta = json.loads((pack / "scenario.json").read_text(encoding="utf-8"))
    assert meta["scenario_id"] == run.scenario_id
    assert (meta["git_commit"], meta["data_hash"]) == ("test", "datahash")
    assert meta["generated_at"] == GENERATED_AT
    assert meta["scenario"]["stock_pct"] == DEMO_SCENARIO.stock_pct
    assert meta["summary"]["banner"].endswith("kits")


def test_zip_holds_every_file_and_is_byte_identical_across_runs(pack, run, tmp_path):
    with zipfile.ZipFile(pack / "commissioner_pack.zip") as archive:
        names = archive.namelist()
    assert names == sorted(names)
    assert "sms/CCC_Ward_01.txt" in names and "dispatch_all.csv" in names
    assert "commissioner_pack.zip" not in names
    write_pack(run, tmp_path, GENERATED_AT, **PROVENANCE)
    assert (tmp_path / "commissioner_pack.zip").read_bytes() == (pack / "commissioner_pack.zip").read_bytes()
