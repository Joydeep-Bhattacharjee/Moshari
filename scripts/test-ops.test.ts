// Python -> TypeScript parity for the Phase 2 decision core.
// tests/fixtures/ops_parity.json is written by `python -m src.ops.parity`; every scenario
// in it is re-run here through src/lib/ops and must give the same numbers and text.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { allocateUnits, regionSummary } from "../src/lib/ops/allocate.ts";
import { renderBrief } from "../src/lib/ops/brief.ts";
import { supplyUnits } from "../src/lib/ops/demand.ts";
import { gsmLength, renderSms, renderWhatsapp, smsSegments } from "../src/lib/ops/dispatchText.ts";
import { buildNotices } from "../src/lib/ops/notices.ts";
import { runScenario } from "../src/lib/ops/pipeline.ts";
import { sha1Hex } from "../src/lib/ops/sha1.ts";
import type { OpsConfig, OpsForecasts, Scenario } from "../src/lib/ops/types.ts";

interface FixtureScenario {
  scenario: Scenario;
  scenario_id: string;
  crews: Record<string, number>;
  demand: Record<string, number | string>[];
  allocation: Record<string, number | string>[];
  summary: unknown;
  transfers: unknown[];
  routing_wards: Record<string, number | string>[];
  cities: unknown[];
  prevented: Record<string, number>;
  sms: Record<string, string>;
  whatsapp: Record<string, string>;
  briefs: Record<string, string>;
}

interface Fixtures {
  provenance: { data_hash: string; git_commit: string };
  generated_at: string;
  scenarios: FixtureScenario[];
}

const read = <T>(path: string): T => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8")) as T;
const config = read<OpsConfig>("../public/data/ops/config.json");
const forecasts = read<OpsForecasts>("../public/data/ops/forecasts.json");
const fixtures = read<Fixtures>("../tests/fixtures/ops_parity.json");
const close = (a: number, b: number, tol = 1e-9) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(b));

test("sha1 matches the FIPS 180 test vectors", () => {
  assert.equal(sha1Hex("abc"), "a9993e364706816aba3e25717850c26c9cd0d89d");
  assert.equal(sha1Hex(""), "da39a3ee5e6b4b0d3255bfef95601890afd80709");
  assert.equal(
    sha1Hex("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
    "84983e441c3bd26ebaae4aa1f95129e5e54670f1",
  );
});

test("supply units round .5 down like the dataset", () => {
  assert.equal(supplyUnits(5, 300), 1);
  assert.equal(supplyUnits(15, 300), 4);
  assert.equal(supplyUnits(2.4, 2385), 6);
  assert.equal(supplyUnits(-0.7, 2385), 0);
});

test("Alabama-paradox case stays monotone, as in Python", () => {
  assert.deepEqual(allocateUnits([1, 3, 3], 3, 100)[1], [1, 1, 1]);
  assert.deepEqual(allocateUnits([1, 3, 3], 4, 100)[1], [1, 2, 1]);
});

test("GSM length counts extension characters twice", () => {
  assert.equal(gsmLength("[x]|"), 7);
  assert.equal(smsSegments("a".repeat(161)), 2);
  assert.throws(() => gsmLength("ডেঙ্গু"), /GSM/);
});

test("fixtures were built from this dashboard data", () => {
  assert.deepEqual(fixtures.provenance, {
    data_hash: config.provenance.data_hash,
    git_commit: config.provenance.git_commit,
  });
});

for (const fx of fixtures.scenarios) {
  const s = fx.scenario;
  const label = `${s.asof} ${s.weeks}w stock ${s.stock_pct}% floor ${s.floor_pct}% ${s.confidence} ${s.crews_total} ${s.crew_mode} ${s.band}`;

  test(`parity: ${label}`, () => {
    const run = runScenario(s, config, forecasts);
    assert.equal(run.scenarioId, fx.scenario_id);
    assert.deepEqual(Object.fromEntries(run.crews), fx.crews);

    assert.equal(run.demand.length, fx.demand.length);
    fx.demand.forEach((d, i) => {
      const t = run.demand[i];
      assert.equal(t.ward, d.ward_id);
      assert.ok(close(t.cases, d.cases as number), `${t.ward} cases`);
      assert.deepEqual([t.saline, t.kits, t.beds, t.riskRank], [
        d.saline_bags_needed,
        d.diagnostic_kits_needed,
        d.hospital_beds_required,
        d.risk_rank,
      ]);
    });

    fx.allocation.forEach((a, i) => {
      const t = run.allocation[i];
      assert.deepEqual([t.ward, t.resource, t.priorityRank, t.need, t.floor, t.allocated, t.alert], [
        a.ward_id,
        a.resource,
        a.priority_rank,
        a.need,
        a.floor,
        a.allocated,
        a.alert,
      ]);
      assert.ok(close(t.priority, a.priority as number) && close(t.fill, a.fill as number), `${t.ward} priority/fill`);
    });
    assert.deepEqual(regionSummary(run.allocation), fx.summary);

    assert.deepEqual(
      run.routing.transfers.map((t) => ({ city: t.city, from_ward: t.fromWard, to_ward: t.toWard, patients: t.patients })),
      fx.transfers,
    );
    assert.deepEqual(
      run.routing.wards.map((w) => ({
        ward_id: w.ward,
        required: w.required,
        capacity: w.capacity,
        usable: w.usable,
        sent: w.sent,
        received: w.received,
        unplaced: w.unplaced,
        headroom_after: w.headroomAfter,
      })),
      fx.routing_wards,
    );
    assert.deepEqual(
      run.routing.cities.map((c) => ({
        city: c.city,
        required: c.required,
        capacity: c.capacity,
        moved: c.moved,
        unplaced: c.unplaced,
        alert: c.alert,
      })),
      fx.cities,
    );

    const prevented = new Map<string, number>();
    for (const row of run.sim) prevented.set(row.ward, (prevented.get(row.ward) ?? 0) + row.prevented);
    for (const [ward, value] of Object.entries(fx.prevented)) {
      assert.ok(close(prevented.get(ward)!, value, 1e-9), `${ward} prevented`);
    }

    for (const n of buildNotices(run, fixtures.generated_at, config)) {
      assert.equal(renderSms(n), fx.sms[n.wardId], `${n.wardId} sms`);
      assert.equal(renderWhatsapp(n), fx.whatsapp[n.wardId], `${n.wardId} whatsapp`);
      if (fx.briefs[n.wardId]) assert.equal(renderBrief(n), fx.briefs[n.wardId], `${n.wardId} brief`);
    }
  });
}
