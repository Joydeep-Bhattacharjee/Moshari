// Runs before `npm run dev`: rebuild public/data/*.json from models/model.joblib with the
// project's Python environment, so the dashboard always shows the current model's output.
// Without a working Python environment it keeps the committed snapshot and says so.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";

// MOSHARI_PYTHON lets you point at an environment outside the repo.
const CANDIDATES = [
  process.env.MOSHARI_PYTHON,
  ".venv/Scripts/python.exe",
  ".venv/bin/python",
  "python3",
  "python",
].filter(Boolean);
const NEEDED = "import joblib, numpy, pandas, sklearn";

function findPython() {
  for (const cmd of CANDIDATES) {
    if (cmd.includes("/") && !existsSync(cmd)) continue;
    const probe = spawnSync(cmd, ["-c", NEEDED], { stdio: "ignore" });
    if (probe.status === 0) return cmd;
  }
  return null;
}

const python = findPython();
if (!python) {
  console.warn(
    "[moshari] No Python environment with the model's packages found; using the committed " +
      "forecasts in public/data. To rebuild them from models/model.joblib, run " +
      "`pip install -r requirements.txt` and `python -m src.export`.",
  );
  process.exit(0);
}

console.log(`[moshari] Rebuilding forecasts from models/model.joblib with ${python} ...`);
const started = Date.now();
const run = spawnSync(python, ["-m", "src.export"], { stdio: "inherit" });
if (run.status !== 0) {
  console.warn("[moshari] Export failed; the dashboard will use the committed forecasts in public/data.");
  process.exit(0);
}
console.log(`[moshari] Forecasts rebuilt in ${((Date.now() - started) / 1000).toFixed(1)} s.`);
