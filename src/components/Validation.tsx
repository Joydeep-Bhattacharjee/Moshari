import { FlaskConical, ShieldCheck, TrendingUp } from "lucide-react";
import type { Data } from "plotly.js";
import Chart from "./Chart";
import { validationData } from "../data";
import { CardHeader } from "./DashboardUI";
import type { TEXTS } from "../data";
type TextKey = keyof typeof TEXTS.en;

export default function Validation({
  ward,
  week,
  horizon,
  l,
  t,
}: {
  ward: string;
  week: string;
  horizon: number;
  l: (a: string, b: string) => string;
  t: (k: TextKey) => string;
}) {
  const validation = validationData(ward, horizon);
  const values = validation.values;
  const percent = (n: number) => `${(n * 100).toFixed(1)}%`;
  const x = values.map((p) => p.week);
  const fitData: Data[] = [
    { x, y: values.map((p) => p.lo), type: "scatter", line: { width: 0 }, hoverinfo: "skip" },
    {
      x,
      y: values.map((p) => p.hi),
      type: "scatter",
      line: { width: 0 },
      fill: "tonexty",
      fillcolor: "rgba(59, 130, 246, 0.16)",
      hoverinfo: "skip",
    },
    {
      x,
      y: values.map((p) => p.actual),
      type: "scatter",
      name: t("observed"),
      line: { color: "#1E293B", width: 2.5, shape: "spline" },
    },
    {
      x,
      y: values.map((p) => p.pred),
      type: "scatter",
      name: t("predicted"),
      line: { color: "#208b80", dash: "dot", width: 2.5, shape: "spline" },
    },
  ];
  return (
    <div className="validation-page">
      <div className="validation-notice">
        <FlaskConical size={16} />
        {t("demo")}
      </div>
      <section className="card split-card">
        <CardHeader
          title={l("Test the future. Never leak it.", "ভবিষ্যৎ যাচাই, তথ্য ফাঁস নয়।")}
          subtitle={l(
            "Chronological holdout with a 4-week purge gap and walk-forward evaluation.",
            "সময়ানুক্রমিক বিভাজন, ৪ সপ্তাহের বিরতি ও ধাপে ধাপে যাচাই।",
          )}
          action={<span className="subtle-pill">4 {l("folds", "ধাপ")}</span>}
        />
        <div className="split-timeline">
          <div>
            <strong>{l("Training", "প্রশিক্ষণ")}</strong>
            <span>Jan 2023 – Dec 2024</span>
          </div>
          <div className="purge">
            <strong>{l("4-week gap", "৪ সপ্তাহ বিরতি")}</strong>
            <span>Jan 2025</span>
          </div>
          <div className="testing">
            <strong>{l("Validation", "যাচাই")}</strong>
            <span>Feb – Jun 2025</span>
          </div>
        </div>
        <div className="split-note">
          <ShieldCheck size={14} />
          {l(
            "No shuffled splits. Weather lags and future targets are kept out of the training boundary.",
            "এলোমেলো বিভাজন নয়। ভবিষ্যতের লক্ষ্য ও আবহাওয়ার তথ্য প্রশিক্ষণসীমার বাইরে রাখা হয়।",
          )}
        </div>
      </section>
      <div className="kpi-grid validation-kpis">
        {[
          [
            l("Alert recall", "সতর্কতা শনাক্তকরণ"),
            percent(validation.recall),
            l("High + Critical outbreaks caught", "High + Critical প্রাদুর্ভাব শনাক্ত"),
          ],
          [
            l("Alert precision", "সতর্কতার নির্ভুলতা"),
            percent(validation.precision),
            l("Alerts that became outbreaks", "সতর্কতার পর প্রকৃত প্রাদুর্ভাব"),
          ],
          [
            l("80% interval coverage", "৮০% সীমার অন্তর্ভুক্তি"),
            percent(validation.coverage),
            l("Actuals inside the forecast range", "পূর্বাভাসসীমার মধ্যে প্রকৃত কেস"),
          ],
          [
            l("Model MAE", "মডেলের MAE"),
            validation.model.mae.toFixed(1),
            l("Selected ward · held-out weeks", "নির্বাচিত ওয়ার্ড · স্বতন্ত্র যাচাই"),
          ],
        ].map(([label, value, note]) => (
          <section className="card kpi" key={label}>
            <div className="kpi-label">
              {label}
              <ShieldCheck size={15} />
            </div>
            <div className="kpi-value">{value}</div>
            <p>{note}</p>
          </section>
        ))}
      </div>
      <div className="validation-grid">
        <section className="card">
          <CardHeader
            title={l("Performance over time", "সময়ের সঙ্গে কার্যকারিতা")}
            subtitle={l(
              "Error by walk-forward fold · lower is better",
              "প্রতিটি ধাপে ত্রুটি · কম হওয়া ভালো",
            )}
          />
          <Chart
            label="MAE and RMSE by fold"
            height={235}
            data={[
              {
                x: [1, 2, 3, 4].map((i) => `${l("Fold", "ধাপ")} ${i}`),
                y: validation.folds.map((f) => f.mae),
                type: "bar",
                name: "MAE",
                marker: { color: "#258b82" },
              },
              {
                x: [1, 2, 3, 4].map((i) => `${l("Fold", "ধাপ")} ${i}`),
                y: validation.folds.map((f) => f.rmse),
                type: "bar",
                name: "RMSE",
                marker: { color: "#a7cde9" },
              },
            ]}
            layout={{
              barmode: "group",
              bargap: 0.5,
              showlegend: true,
              legend: { orientation: "h", x: 0.3, y: 1.15 },
              margin: { t: 28, b: 30, l: 35, r: 20 },
            }}
          />
        </section>
        <section className="card">
          <CardHeader
            title={l("A fair comparison", "একটি ন্যায্য তুলনা")}
            subtitle={l("Same split, same wards, same horizon", "একই বিভাজন, ওয়ার্ড ও সময়সীমা")}
          />
          <table className="comparison-table">
            <thead>
              <tr>
                <th>{l("Model", "মডেল")}</th>
                <th>MAE ↓</th>
                <th>RMSE ↓</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{l("Last-week baseline", "গত সপ্তাহের মূল মডেল")}</td>
                <td>{validation.lastWeek.mae.toFixed(1)}</td>
                <td>{validation.lastWeek.rmse.toFixed(1)}</td>
              </tr>
              <tr>
                <td>{l("4-week baseline", "৪ সপ্তাহের মূল মডেল")}</td>
                <td>{validation.seasonal.mae.toFixed(1)}</td>
                <td>{validation.seasonal.rmse.toFixed(1)}</td>
              </tr>
              <tr className="model-highlight">
                <td>
                  DengueRadar <span className="model-label">MODEL</span>
                </td>
                <td>
                  <strong>{validation.model.mae.toFixed(1)}</strong>
                </td>
                <td>
                  <strong>{validation.model.rmse.toFixed(1)}</strong>
                </td>
              </tr>
            </tbody>
          </table>
          <div className="model-improvement">
            <TrendingUp size={16} />
            <span>
              {l(
                "Computed from the same synthetic held-out observations",
                "একই কৃত্রিম স্বতন্ত্র পর্যবেক্ষণ থেকে গণনা করা",
              )}
            </span>
          </div>
        </section>
      </div>
      <div className="validation-grid">
        <section className="card">
          <CardHeader
            title={l("The lag behind the signal", "সংকেতের পেছনের সময় ব্যবধান")}
            subtitle={l(
              "Rainfall-to-cases correlation · lags 0–8 weeks",
              "বৃষ্টিপাত ও কেসের সম্পর্ক · ০–৮ সপ্তাহ",
            )}
          />
          <Chart
            height={228}
            label="Rainfall lag correlation"
            data={[
              {
                x: Array.from({ length: 9 }, (_, i) => `${i}w`),
                y: [0.16, 0.3, 0.58, 0.74, 0.67, 0.43, 0.27, 0.12, 0.05],
                type: "bar",
                marker: {
                  color: [
                    "#bbd5e6",
                    "#bbd5e6",
                    "#258b82",
                    "#258b82",
                    "#258b82",
                    "#bbd5e6",
                    "#bbd5e6",
                    "#bbd5e6",
                    "#bbd5e6",
                  ],
                },
                hovertemplate: "Lag %{x}: %{y:.2f}<extra></extra>",
              },
            ]}
            layout={{
              yaxis: {
                range: [0, 1],
                gridcolor: "#edf1f5",
                title: { text: l("Correlation", "সম্পর্ক"), font: { size: 10 } },
              },
              bargap: 0.45,
            }}
          />
        </section>
        <section className="card confusion-card">
          <CardHeader
            title={l("Did we catch the alert?", "সতর্কতা কি শনাক্ত হয়েছে?")}
            subtitle={l(
              "High + Critical = positive outbreak alert",
              "High + Critical = প্রাদুর্ভাবের সতর্কতা",
            )}
          />
          <div className="confusion-matrix">
            <div />
            <span>{l("Predicted low", "ঝুঁকি কম পূর্বাভাস")}</span>
            <span>{l("Predicted alert", "সতর্কতা পূর্বাভাস")}</span>
            <span>{l("Actual low", "প্রকৃত ঝুঁকি কম")}</span>
            <div className="true-negative">
              <strong>{validation.tn}</strong>
              {l("True negative", "সঠিক নেতিবাচক")}
            </div>
            <div className="false-positive">
              <strong>{validation.fp}</strong>
              {l("False positive", "ভুল ইতিবাচক")}
            </div>
            <span>{l("Actual alert", "প্রকৃত সতর্কতা")}</span>
            <div className="false-negative">
              <strong>{validation.fn}</strong>
              {l("False negative", "ভুল নেতিবাচক")}
            </div>
            <div className="true-positive">
              <strong>{validation.tp}</strong>
              {l("True positive", "সঠিক ইতিবাচক")}
            </div>
          </div>
        </section>
      </div>
      <section className="card">
        <CardHeader
          title={`${ward} · ${l("How closely did we track?", "পূর্বাভাস কতটা কাছাকাছি?")}`}
          subtitle={l(
            "Predicted vs. observed cases with an 80% uncertainty band",
            "৮০% অনিশ্চয়তা সীমাসহ পূর্বাভাসিত ও প্রকৃত কেস",
          )}
        />
        <Chart
          label="Ward predicted versus actual"
          data={fitData}
          layout={{
            hovermode: "x unified",
            xaxis: { tickformat: "%d %b", nticks: 9 },
            margin: { l: 40, r: 25, t: 15, b: 40 },
          }}
          height={260}
        />
        <div className="chart-legend bottom-legend">
          <span>
            <i className="legend-line" />
            {t("observed")}
          </span>
          <span>
            <i className="legend-dash" />
            {t("predicted")}
          </span>
          <span>
            <i className="legend-band" />
            {t("band")}
          </span>
        </div>
      </section>
    </div>
  );
}
