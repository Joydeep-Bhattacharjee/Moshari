import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/data.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const data = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
const { WARDS, WEEKS, forecast, series, priority, validationData, TEXTS, label_text } = data;

test("all wards and horizons have valid intervals and consistent timelines", () => {
  for (const ward of WARDS)
    for (const horizon of [2, 3, 4]) {
      const baseline = forecast(ward, WEEKS[0], horizon);
      assert.ok(baseline.lo <= baseline.pred && baseline.pred <= baseline.hi);
      assert.equal(baseline.actual, null);
      const timeline = series(ward, WEEKS[0], horizon, 1);
      assert.equal(timeline.length, 26);
      assert.equal(timeline.at(-1).pred, baseline.pred);
      assert.equal(timeline.at(-1).week, baseline.target);
      assert.ok(
        timeline
          .filter((p) => p.week > WEEKS[0])
          .every((p) => p.actual === null && p.rain === null),
      );
    }
});

test("rainfall changes forecasts but never changes observed cases", () => {
  for (const ward of WARDS) {
    const low = forecast(ward, WEEKS[8], 3, 0.5);
    const high = forecast(ward, WEEKS[8], 3, 2);
    assert.ok(high.pred >= low.pred);
    assert.equal(high.actual, low.actual);
    assert.deepEqual(
      series(ward, WEEKS[8], 3, 0.5).map((p) => p.actual),
      series(ward, WEEKS[8], 3, 2).map((p) => p.actual),
    );
  }
});

test("priority ranks by tier, then descending cases, for every week", () => {
  const tierOrder = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  for (const week of WEEKS)
    for (const horizon of [2, 3, 4]) {
      const rows = priority(week, horizon);
      assert.equal(rows.length, WARDS.length);
      rows.slice(1).forEach((r, i) => {
        const previous = rows[i];
        assert.ok(tierOrder[previous.tier] <= tierOrder[r.tier]);
        if (previous.tier === r.tier) assert.ok(previous.pred >= r.pred);
      });
    }
});

test("held-out validation has four folds and consistent alert denominators", () => {
  for (const ward of WARDS)
    for (const horizon of [2, 3, 4]) {
      const v = validationData(ward, horizon);
      assert.equal(v.folds.length, 4);
      assert.equal(v.tn + v.fp + v.fn + v.tp, v.values.length);
      assert.equal(v.recall, v.tp / Math.max(1, v.tp + v.fn));
      assert.equal(v.precision, v.tp / Math.max(1, v.tp + v.fp));
      assert.ok(
        v.values.every(
          (p) => p.week >= "2025-02-03" && p.week <= "2025-06-30" && p.actual !== null,
        ),
      );
      assert.ok(v.coverage >= 0 && v.coverage <= 1);
    }
});

test("all language keys exist and modes resolve synchronously", () => {
  assert.deepEqual(Object.keys(TEXTS.en), Object.keys(TEXTS.bn));
  assert.equal(label_text("Forecast", "পূর্বাভাস", "EN"), "Forecast");
  assert.equal(label_text("Forecast", "পূর্বাভাস", "বাংলা"), "পূর্বাভাস");
  assert.equal(label_text("Forecast", "পূর্বাভাস", "EN + বাংলা"), "Forecast / পূর্বাভাস");
});
