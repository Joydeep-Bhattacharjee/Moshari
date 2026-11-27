// "Explain this number" (PRD 7): every figure for one ward, with the formula that made it.
import { useEffect } from "react";
import { X } from "lucide-react";
import { priorityScores } from "../lib/ops/allocate.ts";
import { supplyUnits } from "../lib/ops/demand.ts";
import type { ScenarioRun } from "../lib/ops/pipeline.ts";
import type { OpsConfig, Scenario, WindowRow } from "../lib/ops/types.ts";
import { BEDS, KITS, SALINE } from "../lib/ops/types.ts";
import { fmt1, fmtPct } from "./format";
import { AlertPill, TierBadge } from "./ui";

type Props = { ward: string; run: ScenarioRun; config: OpsConfig; scenario: Scenario; onClose: () => void };

export function ExplainDrawer({ ward, run, config, scenario, onClose }: Props) {
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  const c = config.constants;
  const per1000 = c.supply_per_1000;
  const densityRef = Math.max(...config.wards.map((w) => w.density));
  const ranked = priorityScores(run.demand, c, densityRef).find((d) => d.ward === ward)!;
  const maxCases = Math.max(...run.demand.map((d) => d.cases));
  const plan = run.planWindow.filter((r) => r.ward === ward).sort((a, b) => a.weekAhead - b.weekAhead);
  const sim = run.sim.filter((s) => s.ward === ward).sort((a, b) => a.weekAhead - b.weekAhead);
  const saline = run.allocation.find((a) => a.ward === ward && a.resource === SALINE)!;
  const kits = run.allocation.find((a) => a.ward === ward && a.resource === KITS)!;
  const route = run.routing.wards.find((w) => w.ward === ward)!;
  const planned = (r: WindowRow) => Math.max(scenario.confidence === "bad" ? r.p90 : r.expected, 0);
  const basis = scenario.confidence === "bad" ? "P90 (bad case)" : "expected (likely)";
  const crews = run.crews.get(ward) ?? 0;
  const h = String(plan[0].modelHorizon);
  const cutoffs = c.thresholds[h].map((t) => (t * c.decision_scale[h]).toFixed(1)).join(" / ");
  const supplyLines = (key: string) =>
    plan
      .map((r) => `${r.targetWeek}: ${per1000[key] / 1000} × ${fmt1(planned(r))} → ${supplyUnits(planned(r), per1000[key])}`)
      .join("\n");
  const forecastLines = plan
    .map(
      (r) =>
        `${r.targetWeek}  ${fmt1(r.expected)} cases (P10 ${fmt1(r.p10)} – P90 ${fmt1(r.p90)})  ` +
        `${c.tiers[r.tierRank]} · driver: ${r.topDriver} · ${r.modelHorizon}-week model`,
    )
    .join("\n");
  const priorityLines = [
    `${c.weights.risk} × ${ranked.riskNorm} (risk)`,
    `+ ${c.weights.density} × ${ranked.density.toFixed(0)} / ${densityRef.toFixed(0)} (density)`,
    `+ ${c.weights.cases} × ${fmt1(ranked.cases)} / ${fmt1(maxCases)} (cases)`,
    `= ${ranked.priority.toFixed(3)}  → rank ${ranked.priorityRank}`,
  ].join("\n");
  const allocationLines = [
    `stock = floor(${scenario.stock_pct}% × region need)`,
    `saline: floor ${saline.floor} (ceil ${scenario.floor_pct}% × ${saline.need}) + priority top-up ` +
      `${saline.allocated - saline.floor} = ${saline.allocated} (${fmtPct(saline.fill)})`,
    `kits:   floor ${kits.floor} + top-up ${kits.allocated - kits.floor} = ${kits.allocated} (${fmtPct(kits.fill)})`,
  ].join("\n");
  const crewLines = [
    `${crews} crews → water-logging cut ${fmtPct(sim[0]?.reduction ?? 0)} (${scenario.band} band)`,
    ...sim.map(
      (s) =>
        `${s.targetWeek}: index ${s.waterlog.toFixed(3)} → ${s.waterlogAfter.toFixed(3)}, ` +
        `cases × ${s.effectRatio.toFixed(4)}, prevented ${s.prevented.toFixed(2)}`,
    ),
  ].join("\n");
  const bedLines = [
    `need = peak week of round_half_down(${per1000[BEDS] / 1000} × cases) = ${route.required}`,
    `capacity ${route.capacity} (${config.provenance.capacity_source}), usable ${route.usable}`,
    `sent ${route.sent} · received ${route.received} · unplaced ${route.unplaced}`,
  ].join("\n");

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`How ${ward}'s numbers were derived`}>
        <header>
          <div>
            <h2>{ward}</h2>
            <p>
              {saline.city} · priority rank {saline.priorityRank} of {run.demand.length}{" "}
              <TierBadge rank={saline.riskRank} />
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>
        <div className="drawer-body">
          <h3>Forecast</h3>
          <div className="formula">{forecastLines}</div>
          <p className="ops-note">
            Risk is the highest weekly tier. Tier cut-offs for the {h}-week model: {cutoffs} cases a week (training
            P50 / P75 / P90 × the alert scale {c.decision_scale[h]}).
          </p>
          <h3>Priority</h3>
          <div className="formula">{priorityLines}</div>
          <h3>Saline and test kits</h3>
          <p className="ops-note">Dataset formula on each week's {basis} forecast, rounded half down:</p>
          <div className="formula">{`Saline\n${supplyLines(SALINE)}\nneed = ${saline.need}\n\nTest kits\n${supplyLines(KITS)}\nneed = ${kits.need}`}</div>
          <div className="formula">{allocationLines}</div>
          <p className="ops-note">
            Saline <AlertPill alert={saline.alert} /> · kits <AlertPill alert={kits.alert} /> — critical below{" "}
            {c.critical_fill * 100}% fill, or below {c.high_risk_fill * 100}% for High and Critical wards.
          </p>
          <h3>Spray crews</h3>
          <div className="formula">{crewLines}</div>
          <h3>Hospital beds</h3>
          <div className="formula">{bedLines}</div>
        </div>
      </aside>
    </>
  );
}
