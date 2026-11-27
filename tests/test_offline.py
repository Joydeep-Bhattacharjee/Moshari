"""Offline resilience (PRD 6.5): with every socket blocked, the whole chain rebuilds the
committed export pack exactly: every text file byte for byte, the zip entry for entry."""
import json
import re
import socket
import zipfile

import pytest

from src import config as cfg
from src.ops import selfcheck
from src.ops.export_pack import EXPORT_DIR, write_pack
from src.ops.pipeline import load_context, run_scenario
from src.ops.scenario import Scenario

pytestmark = pytest.mark.skipif(
    not (cfg.MODEL_PATH.exists() and cfg.ONSITE_DATA_PATH.exists() and (EXPORT_DIR / "scenario.json").exists()),
    reason="model, onsite data or committed export pack not present",
)
NETWORK_IMPORT = re.compile(r"^\s*(?:import|from)\s+(socket|requests|urllib|http|httpx|aiohttp|ftplib)\b", re.M)


def zip_entries(path) -> list[tuple[str, tuple, bytes]]:
    with zipfile.ZipFile(path) as archive:
        return [(info.filename, info.date_time, archive.read(info)) for info in archive.infolist()]


@pytest.fixture
def no_network(monkeypatch):
    selfcheck.block_network(monkeypatch.setattr)


def test_sockets_really_are_blocked(no_network):
    with pytest.raises(selfcheck.NetworkBlocked):
        socket.create_connection(("example.com", 80))
    with pytest.raises(selfcheck.NetworkBlocked):
        socket.getaddrinfo("example.com", 443)


def test_chain_rebuilds_the_committed_pack_exactly_offline(no_network, tmp_path):
    meta = json.loads((EXPORT_DIR / "scenario.json").read_text(encoding="utf-8"))
    ctx = load_context(git_commit=meta["git_commit"])
    assert ctx.data_hash == meta["data_hash"]
    run = run_scenario(Scenario(**meta["scenario"]), ctx)
    assert run.scenario_id == meta["scenario_id"]
    write_pack(run, tmp_path, meta["generated_at"], data_hash=ctx.data_hash, git_commit=meta["git_commit"])
    committed = sorted(p.relative_to(EXPORT_DIR) for p in EXPORT_DIR.rglob("*") if p.is_file())
    rebuilt = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file())
    assert rebuilt == committed
    for rel in committed:
        if rel.suffix == ".zip":
            # Deflate bytes depend on the zlib build (Windows vs Linux), so the archive is
            # compared by what it holds: entry names, timestamps and decompressed bytes.
            assert zip_entries(tmp_path / rel) == zip_entries(EXPORT_DIR / rel), rel
        else:
            assert (tmp_path / rel).read_bytes() == (EXPORT_DIR / rel).read_bytes(), rel


def test_decision_core_has_no_network_imports():
    for path in sorted((cfg.ROOT / "src" / "ops").glob("*.py")):
        if path.name == "selfcheck.py":
            continue  # imports socket only to block it
        assert not NETWORK_IMPORT.search(path.read_text(encoding="utf-8")), path.name


def test_selfcheck_prints_the_offline_banner(capsys):
    assert selfcheck.main() == 0
    out = capsys.readouterr().out
    assert "OFFLINE MODE" in out and "model" in out and "data" in out and "templates" in out
