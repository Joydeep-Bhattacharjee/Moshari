import { useEffect, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";
import type { Data, Layout, Config } from "plotly.js";

export default function Chart({
  data,
  layout,
  height = 260,
  label,
}: {
  data: Data[];
  layout?: Partial<Layout>;
  height?: number;
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!ref.current) return;
    const element = ref.current;
    let active = true;
    setFailed(false);
    const base: Partial<Layout> = {
      autosize: true,
      height,
      margin: { l: 38, r: 15, t: 10, b: 35 },
      font: { family: "Inter, sans-serif", size: 10, color: "#64748b" },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      hoverlabel: {
        bgcolor: "#fff",
        bordercolor: "#e2e8f0",
        font: { family: "Inter", size: 12, color: "#0f172a" },
      },
      xaxis: { showgrid: false, zeroline: false, fixedrange: true },
      yaxis: { gridcolor: "#edf1f5", zeroline: false, fixedrange: true },
      showlegend: false,
    };
    const config: Partial<Config> = {
      responsive: true,
      displayModeBar: false,
      displaylogo: false,
      scrollZoom: false,
    };
    try {
      void Plotly.react(element, data, { ...base, ...layout }, config).catch(() => {
        if (active) setFailed(true);
      });
    } catch {
      setFailed(true);
    }
    const observer = new ResizeObserver(() => {
      if (element.isConnected) void Promise.resolve(Plotly.Plots.resize(element)).catch(() => {});
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      active = false;
      Plotly.purge(element);
    };
  }, [data, layout, height]);
  return (
    <div className="chart-container">
      {failed && (
        <p className="error-notice" role="status">
          {label}: Chart unavailable / চার্ট দেখানো যাচ্ছে না।
        </p>
      )}
      <div
        ref={ref}
        className="plot-chart"
        style={{ height, display: failed ? "none" : undefined }}
        role="img"
        aria-label={label}
      />
    </div>
  );
}
