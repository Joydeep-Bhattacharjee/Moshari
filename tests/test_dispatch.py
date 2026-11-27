"""Dispatch notices: SMS, WhatsApp and the printable brief (PRD 6.4 acceptance)."""
import dataclasses

import pytest

from src import config as cfg
from src.ops.brief import render_brief
from src.ops.dispatch_text import gsm_length, render_sms, render_whatsapp, short_ward, sms_segments
from src.ops.notices import Notice, WeekBand, actions, build_notices
from src.ops.pipeline import load_context, run_scenario
from src.ops.scenario import Scenario

needs_model = pytest.mark.skipif(
    not (cfg.MODEL_PATH.exists() and cfg.ONSITE_DATA_PATH.exists()),
    reason="trained model or onsite data not present",
)
GENERATED_AT = "2026-11-27 10:15"


def make_notice(**overrides) -> Notice:
    """PRD 6.4 example ward: DNCC_Ward_05, short on saline, sending one patient."""
    base = dict(
        ward_id="DNCC_Ward_05",
        city="Dhaka North",
        risk="Critical",
        risk_rank=3,
        cases_p50=14,
        cases_p90=19,
        weeks=(
            WeekBand("2025-07-07", 14.2, 9.1, 19.0, 12.0),
            WeekBand("2025-07-14", 11.0, 6.5, 16.3, None),
        ),
        saline_allocated=10,
        saline_required=33,
        kits_allocated=16,
        kits_required=16,
        beds_required=4,
        beds_capacity=3,
        capacity_source="proxy P75",
        crews=2,
        sends=(("DNCC_Ward_16", 1),),
        receives=(),
        unplaced=0,
        asof="2025-06-30",
        scenario_id="3fa9c2d1",
        generated_at=GENERATED_AT,
    )
    return Notice(**{**base, **overrides})


QUIET = dict(saline_allocated=33, sends=(), beds_required=3, risk="Low", risk_rank=0, crews=0)


# --- SMS ---------------------------------------------------------------------------

def test_gsm_length_counts_extension_characters_twice_and_rejects_others():
    assert gsm_length("Saline 10/33; Kits") == 18
    assert gsm_length("[x]|") == 7
    with pytest.raises(ValueError, match="GSM"):
        gsm_length("ডেঙ্গু")


@pytest.mark.parametrize(("length", "segments"), [(1, 1), (160, 1), (161, 2), (306, 2), (307, 3)])
def test_segment_count_follows_gsm_concatenation(length, segments):
    assert sms_segments("a" * length) == segments


def test_short_ward_keeps_the_number_within_the_city():
    assert short_ward("DNCC_Ward_16") == "W16"
    assert short_ward("CCC_Ward_01") == "W01"


def test_sms_golden_for_the_prd_example_ward():
    assert render_sms(make_notice()) == (
        "DENGUE 2025-06-30 DNCC_Ward_05 DhakaN CRITICAL 14c/wk (P90 19); Saline 10/33; "
        "Kits 16/16; Beds 4/cap3; Crews 2; DEFICIT; Send 1>W16; ID 3fa9c2d1 2026-11-27 10:15"
    )


def test_quiet_ward_fits_one_segment_without_deficit_flag():
    sms = render_sms(make_notice(**QUIET))
    assert "DEFICIT" not in sms and "Send" not in sms
    assert sms_segments(sms) == 1


def test_receiving_and_escalating_wards_say_so():
    sms = render_sms(make_notice(sends=(), receives=(("DNCC_Ward_12", 2),), unplaced=3))
    assert "Recv 2<W12" in sms and "Escalate 3pt" in sms


# --- Actions, WhatsApp, brief -------------------------------------------------------

def test_actions_cover_shortfall_transfer_crews_and_reporting():
    steps = actions(make_notice(receives=(("DNCC_Ward_12", 2),), unplaced=1, kits_allocated=10))
    text = " ".join(steps)
    for phrase in ("23 more saline bags", "6 more test kits", "Transfer 1 patient to DNCC_Ward_16",
                   "Prepare 2 beds for patients from DNCC_Ward_12", "Escalate", "2 spray crews",
                   "Report cases daily"):
        assert phrase in text


def test_quiet_ward_gets_routine_surveillance():
    assert actions(make_notice(**QUIET)) == ("Routine surveillance: no extra action needed this window.",)


def test_whatsapp_has_bold_headers_bullets_and_actions():
    msg = render_whatsapp(make_notice())
    assert msg.startswith("*DENGUE ALERT")
    assert "\n• Saline: 10 / 33 bags (DEFICIT 23)" in msg
    assert "\n*Actions*\n1. " in msg
    assert "Send 1 patient to DNCC_Ward_16" in msg


def test_brief_is_a4_print_html_with_chart_and_escaped_values():
    html = render_brief(make_notice(ward_id="<b>W</b>"))
    assert html.startswith("<!doctype html>")
    assert "@page { size: A4" in html
    assert "<svg" in html and "&lt;b&gt;W&lt;/b&gt;" in html
    assert "<b>W</b>" not in html


@pytest.mark.parametrize("render", [render_sms, render_whatsapp, render_brief])
def test_every_format_carries_every_required_field(render):
    notice = make_notice()
    text = render(notice)
    for value in ("DNCC_Ward_05", "14", "19", "10", "33", "16", "2025-06-30", "3fa9c2d1", GENERATED_AT):
        assert value in text, (render.__name__, value)
    assert notice.risk.upper() in text.upper()
    assert ("DhakaN" in text) or ("Dhaka North" in text)
    assert "DEFICIT" in text.upper()


def test_notice_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_notice().crews = 3


# --- Real scenario ------------------------------------------------------------------

@pytest.fixture(scope="module")
def ctx():
    return load_context(git_commit="test")


@needs_model
@pytest.mark.parametrize(
    "scenario",
    [Scenario(stock_pct=60), Scenario(stock_pct=30, confidence="bad"), Scenario(asof="2025-07-14", weeks=4)],
)
def test_sms_length_rules_hold_for_all_60_wards(ctx, scenario):
    notices = build_notices(run_scenario(scenario, ctx), GENERATED_AT)
    assert len(notices) == 60
    for notice in notices:
        segments = sms_segments(render_sms(notice))
        acting = notice.deficit or notice.sends or notice.receives
        assert segments <= 3 if acting else segments == 1, notice.ward_id


@needs_model
def test_notice_numbers_match_the_allocation_and_routing_tables(ctx):
    run = run_scenario(Scenario(stock_pct=60, crews_total=20), ctx)
    notices = {n.ward_id: n for n in build_notices(run, GENERATED_AT)}
    alloc = run.allocation.set_index([cfg.WARD_COL, "resource"])
    routing = run.routing.wards.set_index(cfg.WARD_COL)
    for ward, n in notices.items():
        assert n.saline_allocated == alloc.loc[(ward, cfg.SALINE_COL), "allocated"]
        assert n.kits_required == alloc.loc[(ward, cfg.KITS_COL), "need"]
        assert n.beds_required == routing.loc[ward, "required"]
        assert n.unplaced == routing.loc[ward, "unplaced"]
        assert sum(k for _, k in n.sends) == routing.loc[ward, "sent"]
        assert sum(k for _, k in n.receives) == routing.loc[ward, "received"]
        assert n.crews == run.crews.loc[ward]
        assert n.scenario_id == run.scenario_id


@needs_model
def test_same_run_gives_identical_notices(ctx):
    run = run_scenario(Scenario(stock_pct=60), ctx)
    first, second = build_notices(run, GENERATED_AT), build_notices(run, GENERATED_AT)
    assert [render_brief(n) for n in first] == [render_brief(n) for n in second]
