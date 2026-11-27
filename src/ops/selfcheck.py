"""Startup self-check for the offline demo (PRD 6.5): python -m src.ops.selfcheck

Blocks every socket for the duration of the check, then loads the model and data, runs
the committed demo scenario end to end and renders all three notice formats. Prints:
    OFFLINE MODE ✓  model ✓  data ✓  templates ✓
Exit code 1 if any part fails; the failing part is named.
"""
from __future__ import annotations

import json
import socket
import sys
from collections.abc import Callable

from src.ops.brief import render_brief
from src.ops.dispatch_text import render_sms, render_whatsapp
from src.ops.export_pack import EXPORT_DIR
from src.ops.notices import build_notices
from src.ops.pipeline import load_context, run_scenario
from src.ops.scenario import Scenario

OK, FAIL = "✓", "✗"
SOCKET_ENTRY_POINTS = ("socket", "create_connection", "getaddrinfo")


class NetworkBlocked(RuntimeError):
    """Raised by any attempt to open a network connection while the network is blocked."""


def _refuse(*_args, **_kwargs):
    raise NetworkBlocked("network access attempted while offline mode is enforced")


def block_network(setattr_: Callable) -> None:
    """Replace socket entry points with _refuse, using a setattr-like function
    (pytest's monkeypatch.setattr in tests, plain setattr with restore in main)."""
    for name in SOCKET_ENTRY_POINTS:
        setattr_(socket, name, _refuse)


def _run_checks() -> dict[str, bool]:
    results = {"model": False, "data": False, "templates": False}
    meta = json.loads((EXPORT_DIR / "scenario.json").read_text(encoding="utf-8"))
    ctx = load_context(git_commit=meta["git_commit"])
    results["model"] = True
    results["data"] = ctx.data_hash == meta["data_hash"]
    run = run_scenario(Scenario(**meta["scenario"]), ctx)
    notice = build_notices(run, meta["generated_at"])[0]
    results["templates"] = all(render(notice) for render in (render_sms, render_whatsapp, render_brief))
    return results


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    saved = {name: getattr(socket, name) for name in SOCKET_ENTRY_POINTS}
    try:
        block_network(setattr)
        results = _run_checks()
    except Exception as exc:  # name the failing part instead of a stack trace (PRD 8)
        print(f"OFFLINE MODE {FAIL}  self-check failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        for name, original in saved.items():
            setattr(socket, name, original)
    parts = "  ".join(f"{name} {OK if ok else FAIL}" for name, ok in results.items())
    print(f"OFFLINE MODE {OK}  {parts}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
