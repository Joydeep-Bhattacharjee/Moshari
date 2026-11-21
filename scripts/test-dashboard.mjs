import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";
import ts from "typescript";

// Load src/data.ts as an ES module and feed it the files written by `python -m src.export`.
const source = readFileSync(new URL("../src/data.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
});
const data = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
const readJson = (name) =>
  JSON.parse(readFileSync(new URL(`../public/data/${name}`, import.meta.url), "utf8"));
const validationFile = readJson("validation.json");
data.initData(readJson("dashboard.json"), validationFile);

const {
  WARDS,
  WEEKS,
  forecast,
  series,
  priority,
  validationData,
  driverValues,
  driverSentence,
  tierFor,
  actualTierFor,
  TEXTS,
  label_text,
} = data;
const MONSOON = "2025-08-04";

test("all 60 real wards and the 2024-2025 forecast weeks are loaded", () => {
  assert.equal(WARDS.length, 60);
  assert.ok(WARDS.includes("DSCC_Ward_05"));
  assert.equal(WEEKS[0], "2025-12-29"); // latest first
  assert.equal(WEEKS.at(-1), "2024-01-01");
});

test("intervals contain the forecast and timelines end at the forecast", () => {
  for (const ward of WARDS)
    for (const horizon of [2, 3, 4])
      for (const week of [WEEKS[0], MONSOON]) {
        const f = forecast(ward, week, horizon);
        assert.ok(f.lo >= 0 && f.lo <= f.pred && f.pred <= f.hi, `${ward} ${week} h${horizon}`);
        const timeline = series(ward, week, horizon, 1);
        assert.equal(timeline.length, 26);
        assert.equal(timeline.at(-1).pred, f.pred);
        assert.equal(timeline.at(-1).week, f.target);
      }
  // the latest week's targets lie beyond the data, so nothing is observed yet
  assert.equal(forecast("DSCC_Ward_05", WEEKS[0], 3).actual, null);
  const future = series("DSCC_Ward_05", WEEKS[0], 3, 1).filter((p) => p.week > "2025-12-29");
  assert.ok(future.length > 0 && future.every((p) => p.actual === null && p.rain === null));
});

test("forecasts match the Python model output", () => {
  const f = forecast("DSCC_Ward_05", MONSOON, 3);
  assert.equal(f.pred, 4.9); // 4.88 from src.predict, rounded to one decimal
  assert.equal(f.actual, 10);
  assert.equal(driverValues("DSCC_Ward_05", MONSOON, 3).length, 6);
});

test("more rain never lowers the 2- and 3-week forecasts and never changes what happened", () => {
  for (const ward of WARDS) {
    for (const horizon of [2, 3]) {
      const low = forecast(ward, MONSOON, horizon, 0.5);
      const high = forecast(ward, MONSOON, horizon, 2);
      assert.ok(high.pred >= low.pred, `${ward} h${horizon}`);
      assert.equal(high.actual, low.actual);
    }
    assert.deepEqual(
      series(ward, MONSOON, 3, 0.5).map((p) => p.actual),
      series(ward, MONSOON, 3, 2).map((p) => p.actual),
    );
  }
  // the 4-week model is only partly monotonic (see MODEL_CARD.md), so check the city total
  const total = (m) => WARDS.reduce((s, w) => s + forecast(w, MONSOON, 4, m).pred, 0);
  assert.ok(total(2) > total(1));
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

test("forecast tiers use the alert-tuned cut-offs, observed tiers the training thresholds", () => {
  // thresholds 5 / 9 / 14 cases; at 3 weeks forecasts use x0.8 -> 4 / 7.2 / 11.2
  assert.equal(tierFor(4, 3), "Medium");
  assert.equal(actualTierFor(4, 3), "Low");
  assert.equal(actualTierFor(14, 3), "Critical");
});

test("validation shows the measured holdout results", () => {
  const split = validationFile.split;
  for (const ward of WARDS.slice(0, 6))
    for (const horizon of [2, 3, 4]) {
      const v = validationData(ward, horizon);
      assert.equal(v.folds.length, 4);
      assert.ok(Math.abs(v.recall - v.tp / (v.tp + v.fn)) < 1e-3);
      assert.ok(Math.abs(v.precision - v.tp / (v.tp + v.fp)) < 1e-3);
      assert.ok(v.values.length > 70);
      assert.ok(v.values.every((p) => p.week >= split.holdout_start && p.week <= split.data_end));
      assert.ok(v.model.rmse < v.seasonal.rmse && v.model.rmse < v.wardMean.rmse);
    }
});

test("driver sentences and language keys resolve in every mode", () => {
  assert.match(driverSentence("DSCC_Ward_05", MONSOON, 3, "EN"), /risk in 3 weeks/);
  assert.match(driverSentence("DSCC_Ward_05", MONSOON, 3, "বাংলা"), /3 সপ্তাহ পর/);
  assert.deepEqual(Object.keys(TEXTS.en), Object.keys(TEXTS.bn));
  assert.equal(label_text("Forecast", "পূর্বাভাস", "EN + বাংলা"), "Forecast / পূর্বাভাস");
});
