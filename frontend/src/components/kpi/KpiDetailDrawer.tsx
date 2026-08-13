"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { LoadingState } from "@/components/common/LoadingState";
import { useKpiDetail } from "@/hooks/useKpis";
import { useKpiHistory } from "@/hooks/useKpiHistory";
import { formatNumber, formatTime } from "@/lib/utils";

/**
 * KPI drill-down as a centered viewport popup.
 * Portaled to document.body so parent transform/animation cannot clip it.
 */
export function KpiDetailDrawer({
  kpiId,
  onClose,
}: {
  kpiId: string;
  onClose: () => void;
}) {
  const [mounted, setMounted] = useState(false);
  const detailQuery = useKpiDetail(kpiId);
  const { history, isLoading: histLoading } = useKpiHistory(kpiId, 48);
  const kpi = detailQuery.data;
  const accent = kpi?.accent ?? "#6BC1F2";
  const digits = kpi && kpi.unit === "%" && kpi.value > 90 ? 2 : 1;
  const chartData = history.map((p) => ({
    t: p.timestamp,
    v: p.value,
    label: formatTime(p.timestamp),
  }));

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  if (!mounted) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4 sm:p-6"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={kpi?.name ? `${kpi.name} KPI detail` : "KPI detail"}
        className="flex max-h-[min(90vh,860px)] w-full max-w-[720px] flex-col overflow-hidden rounded-[8px] border border-[var(--line)] bg-[var(--panel)] shadow-[0_24px_80px_rgba(0,0,0,0.55)]"
        style={{
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.03), transparent 36%), var(--panel)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex shrink-0 items-start justify-between border-b border-[var(--line)] px-5 py-4">
          <div>
            <div className="vl-label">KPI Analytics</div>
            <h2 className="font-display mt-1 text-[22px] font-semibold text-[var(--text)]">
              {kpi?.name ?? "Loading…"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[6px] border border-[var(--line-bright)] px-2.5 py-1 text-[11px] text-[var(--muted)] transition-colors hover:border-[rgba(107,193,242,0.45)] hover:text-[var(--text)]"
          >
            Close
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {detailQuery.isLoading || !kpi ? (
            <LoadingState label="Loading KPI detail…" />
          ) : detailQuery.isError ? (
            <div className="rounded-[6px] border border-[var(--red)]/40 bg-[var(--red-dim)] px-3 py-4 text-[12px] text-[var(--red)]">
              Unable to load KPI detail. Close and try again.
            </div>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Tile label="Current Value" value={`${formatNumber(kpi.value, digits)}${kpi.unit}`} />
                <Tile label="Previous" value={`${formatNumber(kpi.previous_value, digits)}${kpi.unit}`} />
                <Tile label="Baseline" value={`${formatNumber(kpi.baseline, digits)}${kpi.unit}`} />
                <Tile label="Target" value={`${formatNumber(kpi.target, digits)}${kpi.unit}`} />
                <Tile
                  label="Improvement"
                  value={`${kpi.improvement >= 0 ? "+" : ""}${formatNumber(kpi.improvement, digits)}${kpi.unit}`}
                  accent={kpi.improvement >= 0 ? "var(--green)" : "var(--red)"}
                />
                <Tile
                  label="Trend / Status"
                  value={`${kpi.trend} · ${String(kpi.status).replace(/_/g, " ")}`}
                />
              </div>

              <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Tile label="Lots" value={String(kpi.lots)} compact />
                <Tile label="Wafers" value={String(kpi.wafers)} compact />
                <Tile label="Testers" value={String(kpi.testers)} compact />
                <Tile label="Sites" value={String(kpi.sites)} compact />
              </div>

              <div className="vl-label mb-2">Historical Trend</div>
              <div className="mb-5 h-[220px] rounded-[6px] border border-[var(--line)] bg-[var(--panel-2)] p-2">
                {histLoading ? (
                  <LoadingState label="Loading history…" />
                ) : chartData.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-[12px] text-[var(--muted)]">
                    No history points yet
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <CartesianGrid stroke="#1C2532" strokeDasharray="3 3" />
                      <XAxis dataKey="label" tick={{ fill: "#56637A", fontSize: 10 }} />
                      <YAxis tick={{ fill: "#56637A", fontSize: 10 }} width={36} />
                      <Tooltip
                        contentStyle={{
                          background: "#0D131C",
                          border: "1px solid #2A3648",
                          fontSize: 11,
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="v"
                        stroke={accent}
                        fill={`${accent}33`}
                        strokeWidth={1.8}
                        isAnimationActive={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>

              <div className="vl-label mb-2">Recent Events</div>
              <div className="flex flex-col gap-2">
                {(kpi.recent_events ?? []).length === 0 ? (
                  <div className="rounded-[6px] border border-[var(--line)] bg-[var(--panel-2)] px-3 py-3 text-[11px] text-[var(--muted)]">
                    No recent events for this KPI
                  </div>
                ) : (
                  (kpi.recent_events ?? []).map((ev) => (
                    <div
                      key={ev.event_id}
                      className="rounded-[6px] border border-[var(--line)] bg-[var(--panel-2)] px-3 py-2 text-[11px]"
                    >
                      <div className="mb-1 flex justify-between text-[var(--muted-2)]">
                        <span className="uppercase">{ev.tag}</span>
                        <span className="font-mono">{formatTime(ev.timestamp)}</span>
                      </div>
                      <div className="text-[var(--text)]">{ev.text}</div>
                    </div>
                  ))
                )}
              </div>

              <p className="mt-4 text-[11px] leading-relaxed text-[var(--muted)]">
                {kpi.description}
              </p>
              <p className="mt-2 font-mono text-[10px] text-[var(--muted-2)]">
                Last updated {formatTime(kpi.timestamp)}
              </p>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function Tile({
  label,
  value,
  accent,
  compact,
}: {
  label: string;
  value: string;
  accent?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`rounded-[6px] border border-[var(--line)] bg-[var(--panel-2)] ${compact ? "px-2 py-1.5" : "px-3 py-2"}`}
    >
      <div className="text-[9px] uppercase tracking-[0.08em] text-[var(--muted-2)]">{label}</div>
      <div
        className={`font-mono ${compact ? "text-[12px]" : "text-[14px]"} font-semibold`}
        style={{ color: accent }}
      >
        {value}
      </div>
    </div>
  );
}
