"use client";

import { FileDown } from "lucide-react";
import { useEffect, useState } from "react";
import { downloadShmooReport, resolveShmooPlotUrl } from "@/services/api";
import { useShmooStore } from "@/stores/shmooStore";
import { formatNumber } from "@/lib/utils";

type NarrativeMode = "template" | "llm";

/**
 * M-BIST Shmoo ML Optimization UI — matched to the original localhost:5000 layout:
 * title + 4 KPI cards + full-width characterization plot + report narrative engine.
 */
export function ShmooOptimizationPanel() {
  const sessionId = useShmooStore((s) => s.sessionId);
  const filename = useShmooStore((s) => s.filename);
  const meta = useShmooStore((s) => s.meta);
  const results = useShmooStore((s) => s.results);
  const plotUrl = useShmooStore((s) => s.plotUrl);
  const clear = useShmooStore((s) => s.clear);

  const [narrativeMode, setNarrativeMode] = useState<NarrativeMode>("template");
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  // When a new upload lands, bring this panel into view automatically.
  useEffect(() => {
    if (!sessionId || !results || !meta) return;
    const id = window.setTimeout(() => {
      document
        .getElementById("shmoo-optimization")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
    return () => window.clearTimeout(id);
  }, [sessionId, results, meta]);

  const onDownloadReport = async () => {
    if (!sessionId) return;
    setReportBusy(true);
    setReportError(null);
    try {
      const blob = await downloadShmooReport(sessionId, narrativeMode);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `SHMOO_Analysis_Report_${meta?.die_id ?? "D0001"}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setReportError(err instanceof Error ? err.message : "Report failed");
    } finally {
      setReportBusy(false);
    }
  };

  if (!sessionId || !results || !meta) {
    return (
      <section
        id="shmoo-optimization"
        className="mb-8 overflow-hidden rounded-[10px] border border-[rgba(107,193,242,0.22)] bg-[linear-gradient(180deg,rgba(12,22,38,0.95),rgba(8,14,24,0.98))] px-6 py-8 sm:px-8"
      >
        <header className="mb-6 text-center">
          <h2 className="text-[22px] font-bold tracking-tight text-[#7ec8f0] sm:text-[26px]">
            M-BIST SHMOO ML Optimization System
          </h2>
          <p className="mt-2 text-[12px] leading-relaxed text-[#c5d0dc] sm:text-[13px]">
            Automated Local Boundary Prediction, Guardband Optimization &amp; Executive PDF Reporting
          </p>
        </header>
        <p className="mx-auto max-w-[640px] text-center text-[13px] leading-relaxed text-[var(--muted)]">
          Upload a Shmoo CSV/XLSX from the navbar (file type: <span className="font-mono text-[var(--cyan)]">Shmoo dataset</span>)
          to run VDD × Frequency boundary extraction. Results render in this panel — same layout as the
          standalone M-BIST tool.
        </p>
      </section>
    );
  }

  const imgSrc = plotUrl ? resolveShmooPlotUrl(plotUrl) : null;
  const vMarginMv = results.voltage_margin_v * 1000;
  const fMarginMhz = results.freq_margin_ghz * 1000;

  return (
    <section
      id="shmoo-optimization"
      className="mb-8 scroll-mt-6 overflow-hidden rounded-[10px] border border-[rgba(107,193,242,0.45)] bg-[linear-gradient(180deg,rgba(12,22,38,0.95),rgba(8,14,24,0.98))] px-5 py-7 shadow-[0_0_0_1px_rgba(107,193,242,0.12),0_12px_40px_rgba(0,0,0,0.35)] sm:px-8 sm:py-8"
    >
      <header className="mb-6 text-center">
        <h2 className="text-[22px] font-bold tracking-tight text-[#7ec8f0] sm:text-[26px]">
          M-BIST SHMOO ML Optimization System
        </h2>
        <p className="mt-2 text-[12px] leading-relaxed text-[#c5d0dc] sm:text-[13px]">
          Automated Local Boundary Prediction, Guardband Optimization &amp; Executive PDF Reporting
        </p>
        <p className="mt-3 font-mono text-[11px] text-[var(--muted-2)]">
          {filename ?? "Dataset"} · Lot {meta.lot_id} · Wafer {meta.wafer_id} · Die {meta.die_id}
          <button
            type="button"
            onClick={clear}
            className="ml-3 text-[var(--cyan)] underline-offset-2 hover:underline"
          >
            Clear
          </button>
        </p>
      </header>

      {/* 4 KPI cards — match original tool */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Cross-Val Accuracy"
          value={`${formatNumber(results.cv_accuracy * 100)}%`}
          hint="5-Fold Stratified CV"
        />
        <KpiCard
          label="Recommended VDD"
          value={`${formatNumber(results.recommended_vdd)} V`}
          hint={`+${formatNumber(vMarginMv)} mV Margin`}
        />
        <KpiCard
          label="Recommended Freq"
          value={`${formatNumber(results.recommended_freq)} GHz`}
          hint={`+${formatNumber(fMarginMhz)} MHz Margin`}
        />
        <KpiCard
          label="Boundary R² Fit"
          value={formatNumber(results.boundary_r2)}
          hint={`Slope: ${formatNumber(results.boundary_slope)} GHz/V`}
        />
      </div>

      {/* Full-width characterization plot */}
      <div className="mb-6 overflow-hidden rounded-[8px] border border-[rgba(107,193,242,0.18)] bg-[#0a1220]">
        {imgSrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imgSrc}
            alt="SHMOO Characterization Plot — VDD vs Frequency"
            className="mx-auto h-auto w-full max-w-[1100px] object-contain"
          />
        ) : (
          <div className="flex h-64 items-center justify-center text-[13px] text-[var(--muted)]">
            Plot unavailable
          </div>
        )}
      </div>

      {/* Report Narrative Engine */}
      <div className="rounded-[8px] border border-[rgba(107,193,242,0.18)] bg-[rgba(8,16,28,0.85)] px-5 py-5">
        <div className="mb-4 text-[12px] font-semibold tracking-wide text-[#c5d0dc]">
          Report Narrative Engine:
        </div>

        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          <NarrativeOption
            selected={narrativeMode === "template"}
            onSelect={() => setNarrativeMode("template")}
            title="Option B: Template Engine (Instant)"
          />
          <NarrativeOption
            selected={narrativeMode === "llm"}
            onSelect={() => setNarrativeMode("llm")}
            title="Option A: Local LLM (Phi-3 Mini)"
          />
        </div>

        {reportError ? (
          <div className="mb-3 text-[12px] text-[var(--red)]">{reportError}</div>
        ) : null}

        <button
          type="button"
          disabled={reportBusy}
          onClick={() => void onDownloadReport()}
          className="inline-flex w-full items-center justify-center gap-2 rounded-[8px] bg-[linear-gradient(90deg,#3b82f6_0%,#6366f1_50%,#8b5cf6_100%)] px-5 py-3.5 text-[14px] font-semibold text-white shadow-[0_8px_24px_rgba(59,130,246,0.28)] transition-opacity hover:opacity-95 disabled:opacity-50 sm:w-auto sm:min-w-[320px]"
        >
          <FileDown className="h-4 w-4" />
          {reportBusy ? "Building PDF…" : "Download Executive Report (PDF)"}
        </button>
      </div>
    </section>
  );
}

function KpiCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-[8px] border border-[rgba(107,193,242,0.16)] bg-[rgba(10,18,32,0.9)] px-4 py-4 text-center">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8aa0b8]">
        {label}
      </div>
      <div className="font-mono text-[28px] font-bold leading-none text-[#5ec8f0] sm:text-[30px]">
        {value}
      </div>
      <div className="mt-2 text-[12px] font-medium text-[#3ecf8e]">{hint}</div>
    </div>
  );
}

function NarrativeOption({
  selected,
  onSelect,
  title,
}: {
  selected: boolean;
  onSelect: () => void;
  title: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex items-center gap-2.5 rounded-[8px] border px-4 py-3 text-left text-[13px] transition-colors ${
        selected
          ? "border-[#3b82f6] bg-[rgba(59,130,246,0.12)] text-[#e8f1ff]"
          : "border-[rgba(107,193,242,0.16)] bg-[rgba(12,20,34,0.7)] text-[#9fb0c4] hover:border-[rgba(107,193,242,0.35)]"
      }`}
    >
      <span
        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
          selected ? "border-[#3b82f6]" : "border-[#6b7f96]"
        }`}
      >
        {selected ? <span className="h-2 w-2 rounded-full bg-[#3b82f6]" /> : null}
      </span>
      {title}
    </button>
  );
}
