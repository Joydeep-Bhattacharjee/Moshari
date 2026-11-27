// Phase 2 Operations app: one Scenario drives forecast -> crews -> supplies -> beds ->
// notices, recomputed in the browser on every change. Shares the Phase 1 visual shell.
import { Component, useCallback, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  BedDouble,
  CalendarDays,
  ChevronRight,
  Cpu,
  LayoutDashboard,
  MapPin,
  Package,
  Radar,
  Send,
  ShieldCheck,
  Sprout,
} from "lucide-react";
import { runScenario, type ScenarioRun } from "../lib/ops/pipeline.ts";
import type { OpsConfig, OpsForecasts, Scenario } from "../lib/ops/types.ts";
import { ExplainDrawer } from "./ExplainDrawer";
import { OpsControls } from "./OpsControls";
import { Allocation } from "./screens/Allocation";
import { Dispatch } from "./screens/Dispatch";
import { Overview } from "./screens/Overview";
import { Routing } from "./screens/Routing";
import { System } from "./screens/System";
import { WhatIf } from "./screens/WhatIf";
import type { ScreenProps } from "./screenProps";
import "./ops.css";

type Tab = "overview" | "allocation" | "routing" | "whatif" | "dispatch" | "system";

const TABS: { id: Tab; label: string; icon: typeof Activity; title: string; subtitle: string }[] = [
  {
    id: "overview",
    label: "Command overview",
    icon: LayoutDashboard,
    title: "Command overview",
    subtitle: "Where to act in this window: risk, supplies, beds and alerts for all 60 wards.",
  },
  {
    id: "allocation",
    label: "Allocation",
    icon: Package,
    title: "Supply allocation",
    subtitle: "Saline and test kits under scarce stock: equity floor first, then by priority.",
  },
  {
    id: "routing",
    label: "Surge & routing",
    icon: BedDouble,
    title: "Hospital surge and overflow",
    subtitle: "Bed need against capacity, and patient transfers within each city.",
  },
  {
    id: "whatif",
    label: "What-if",
    icon: Sprout,
    title: "Vector-control what-if",
    subtitle: "Spray crews lower water-logging; the forecast model shows the cases prevented.",
  },
  {
    id: "dispatch",
    label: "Dispatch",
    icon: Send,
    title: "Dispatch notices",
    subtitle: "The SMS, WhatsApp message and printable brief each ward receives.",
  },
  {
    id: "system",
    label: "System",
    icon: Cpu,
    title: "System and provenance",
    subtitle: "Offline status, data and code versions, parameters and assumptions.",
  },
];

class ScreenGuard extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="error-notice" role="alert">
        This screen could not be shown for these settings. Change a setting or reset to defaults.
      </div>
    );
  }
}

type Props = { config: OpsConfig; forecasts: OpsForecasts };
type Result = { run: ScenarioRun; ms: number } | { error: string };

function compute(scenario: Scenario, config: OpsConfig, forecasts: OpsForecasts): Result {
  const started = performance.now();
  try {
    return { run: runScenario(scenario, config, forecasts), ms: performance.now() - started };
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
}

export function OpsApp({ config, forecasts }: Props) {
  const [scenario, setScenario] = useState<Scenario>(config.constants.defaults);
  const [tab, setTab] = useState<Tab>("overview");
  const [explainWard, setExplainWard] = useState<string | null>(null);
  const result = useMemo(() => compute(scenario, config, forecasts), [scenario, config, forecasts]);
  const update = useCallback((patch: Partial<Scenario>) => setScenario((s) => ({ ...s, ...patch })), []);
  const closeExplain = useCallback(() => setExplainWard(null), []);
  const current = TABS.find((t) => t.id === tab)!;

  function screen(props: ScreenProps, ms: number) {
    switch (tab) {
      case "overview":
        return <Overview {...props} />;
      case "allocation":
        return <Allocation {...props} />;
      case "routing":
        return <Routing {...props} />;
      case "whatif":
        return <WhatIf {...props} />;
      case "dispatch":
        return <Dispatch {...props} />;
      case "system":
        return <System {...props} elapsedMs={ms} />;
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#/" aria-label="Operations home" onClick={() => setTab("overview")}>
          <span className="brand-mark">
            <Radar size={25} strokeWidth={1.6} />
          </span>
          <span>
            Moshari<span className="brand-light"> Ops</span>
            <small>FORECAST TO ACTION</small>
          </span>
        </a>
        <div className="workspace-label">
          <span className="workspace-icon">
            <MapPin size={15} />
          </span>
          <div>
            Bangladesh · 5 city corporations
            <small>Operations workspace · 60 wards</small>
          </div>
          <span className="online-dot" />
        </div>
        <OpsControls scenario={scenario} config={config} asofWeeks={forecasts.asof_weeks} onChange={update} />
        <div className="sidebar-bottom">
          <div className="system-title">
            <span className="online-dot" />
            Runs fully offline
            <ShieldCheck size={14} />
          </div>
          <p>
            <a className="ops-link" href="#/forecast">
              <Activity size={13} />
              Phase 1 forecast dashboard
            </a>
          </p>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Operations</span>
            <ChevronRight size={13} />
            <strong>{current.label}</strong>
          </div>
          <div className="topbar-right">
            {"run" in result && (
              <>
                <span className="scenario-chip" title="scenario_id: settings + data hash + code commit">
                  Scenario {result.run.scenarioId}
                </span>
                <span className="offline-chip">recomputed in {result.ms.toFixed(0)} ms</span>
              </>
            )}
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span />
                DENGUE FORECAST-TO-ACTION SYSTEM
              </div>
              <h1>{current.title}</h1>
              <p>{current.subtitle}</p>
            </div>
            <div className="report-date">
              <CalendarDays size={16} />
              <div>
                <span>AS-OF WEEK</span>
                <strong>{scenario.asof}</strong>
              </div>
            </div>
          </div>
          <nav className="tabs" aria-label="Operations sections">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={tab === id ? "active" : ""}
                aria-current={tab === id ? "page" : undefined}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </nav>
          {"error" in result ? (
            <div className="error-notice" role="alert">
              These settings cannot be planned: {result.error}. Reset to defaults to continue.
            </div>
          ) : (
            <ScreenGuard key={`${tab}-${result.run.scenarioId}`}>
              {screen(
                { run: result.run, config, forecasts, scenario, onChange: update, onExplain: setExplainWard },
                result.ms,
              )}
            </ScreenGuard>
          )}
        </main>
      </div>
      {explainWard && "run" in result && (
        <ExplainDrawer
          ward={explainWard}
          run={result.run}
          config={config}
          scenario={scenario}
          onClose={closeExplain}
        />
      )}
    </div>
  );
}
