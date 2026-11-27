// Dispatch (PRD 6.4 / 7): SMS, WhatsApp and A4 brief for each ward, and the bulk pack.
import { useMemo, useState } from "react";
import { ChevronDown, Copy, Download, FileText } from "lucide-react";
import { renderBrief } from "../../lib/ops/brief.ts";
import { gsmLength, renderSms, renderWhatsapp, smsSegments } from "../../lib/ops/dispatchText.ts";
import { buildNotices, type Notice } from "../../lib/ops/notices.ts";
import { buildZip } from "../../lib/ops/zip.ts";
import { csvCell, downloadBlob, nowStamp } from "../format";
import type { ScreenProps } from "../screenProps";
import { Panel, TierBadge } from "../ui";

const CSV_COLUMNS = [
  "ward_id",
  "city",
  "risk",
  "cases_p50",
  "cases_p90",
  "saline_allocated",
  "saline_required",
  "kits_allocated",
  "kits_required",
  "beds_required",
  "beds_capacity",
  "crews",
  "sends",
  "receives",
  "unplaced",
  "deficit",
  "sms_segments",
  "sms",
  "asof",
  "scenario_id",
  "generated_at",
];

function csvRow(n: Notice): string {
  const pairs = (list: [string, number][]) => list.map(([w, k]) => `${w}:${k}`).join(";");
  const sms = renderSms(n);
  const values = [
    n.wardId,
    n.city,
    n.risk,
    n.casesP50,
    n.casesP90,
    n.salineAllocated,
    n.salineRequired,
    n.kitsAllocated,
    n.kitsRequired,
    n.bedsRequired,
    n.bedsCapacity,
    n.crews,
    pairs(n.sends),
    pairs(n.receives),
    n.unplaced,
    n.deficit ? "True" : "False",
    smsSegments(sms),
    sms,
    n.asof,
    n.scenarioId,
    n.generatedAt,
  ];
  return values.map(csvCell).join(",");
}

function packEntries(notices: Notice[]) {
  return [
    ...notices.flatMap((n) => [
      { name: `sms/${n.wardId}.txt`, content: renderSms(n) },
      { name: `whatsapp/${n.wardId}.txt`, content: renderWhatsapp(n) },
      { name: `briefs/${n.wardId}.html`, content: renderBrief(n) },
    ]),
    { name: "dispatch_all.csv", content: [CSV_COLUMNS.join(","), ...notices.map(csvRow)].join("\n") + "\n" },
  ];
}

export function Dispatch({ run, config }: ScreenProps) {
  const generatedAt = useMemo(() => nowStamp(), [run]); // a new timestamp per scenario
  const notices = useMemo(() => buildNotices(run, generatedAt, config), [run, generatedAt, config]);
  const [picked, setPicked] = useState<string | null>(null);
  const [copied, setCopied] = useState("");
  const notice = notices.find((n) => n.wardId === picked) ?? notices.find((n) => n.deficit) ?? notices[0];
  const sms = renderSms(notice);
  const whatsapp = renderWhatsapp(notice);
  const brief = useMemo(() => renderBrief(notice), [notice]);
  const deficits = notices.filter((n) => n.deficit).length;
  const segments = smsSegments(sms);

  async function copy(kind: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
    } catch {
      setCopied("The browser blocked the clipboard: select the text and copy it");
    }
  }
  function openBrief() {
    const url = URL.createObjectURL(new Blob([brief], { type: "text/html" }));
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }
  function generateAll() {
    const zip = buildZip(packEntries(notices));
    downloadBlob(`commissioner_pack_${run.scenarioId}.zip`, new Blob([zip], { type: "application/zip" }));
  }

  return (
    <>
      <div className="ops-actions city-switch">
        <div className="select-wrap">
          <select aria-label="Ward" value={notice.wardId} onChange={(e) => setPicked(e.target.value)}>
            {notices.map((n) => (
              <option key={n.wardId} value={n.wardId}>
                {n.wardId} · {n.city}
                {n.deficit ? " · DEFICIT" : ""}
              </option>
            ))}
          </select>
          <ChevronDown size={14} />
        </div>
        <TierBadge rank={notice.riskRank} />
        <button type="button" className="primary-button" onClick={generateAll}>
          <Download size={14} />
          Generate all 60 (zip)
        </button>
        <span className="ops-note">
          {deficits} of {notices.length} wards have a deficit · scenario {run.scenarioId} · {generatedAt}
        </span>
      </div>
      <div className="ops-grid-even">
        <Panel
          title="SMS"
          subtitle="GSM 7-bit only; one segment unless the ward has a deficit or a transfer"
          action={
            <button type="button" className="ghost-button" onClick={() => copy("SMS copied", sms)}>
              <Copy size={13} />
              Copy
            </button>
          }
        >
          <div className="sms-bubble">{sms}</div>
          <div className="ops-meta">
            <span>{gsmLength(sms)} GSM characters</span>
            <span>
              {segments} segment{segments > 1 ? "s" : ""}
            </span>
          </div>
        </Panel>
        <Panel
          title="WhatsApp"
          action={
            <button type="button" className="ghost-button" onClick={() => copy("WhatsApp copied", whatsapp)}>
              <Copy size={13} />
              Copy
            </button>
          }
        >
          <div className="wa-bubble">{whatsapp}</div>
        </Panel>
      </div>
      {copied && (
        <p className="ops-note" role="status">
          {copied}
        </p>
      )}
      <Panel
        title="A4 brief"
        subtitle="Self-contained HTML; open it and print to PDF"
        action={
          <button type="button" className="ghost-button" onClick={openBrief}>
            <FileText size={13} />
            Open printable brief
          </button>
        }
      >
        <iframe className="brief-frame" title={`Brief for ${notice.wardId}`} sandbox="" srcDoc={brief} />
      </Panel>
    </>
  );
}
