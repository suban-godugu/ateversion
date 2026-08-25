"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { SHMOO_CAPABILITIES } from "@/lib/kpiExternalPages";
import { formatNumber, formatTime } from "@/lib/utils";
import type { Kpi } from "@/types/kpi";

export type ShmooCapabilityMetric = {
  id: string;
  label: string;
  value: number;
  unit: string;
};

export interface OptimizationKpiCardProps {
  kpi: Kpi;
  onOpen?: (kpiId: string) => void;
  /** Embedded SHMOO capability metrics (shown on parent card only). */
  shmooMetrics?: ShmooCapabilityMetric[];
}

export function OptimizationKpiCard({
  kpi,
  onOpen,
  shmooMetrics,
}: OptimizationKpiCardProps) {
  const accent = kpi.accent ?? "#6EE7A8";
  const chartData = (kpi.history ?? []).map((p, i) => ({ i, v: p.value }));
  const digits = kpi.unit === "%" && kpi.value > 90 ? 2 : 1;
  const isShmoo = kpi.id === "m_bist_shmoo";

  return (
    <button
      type="button"
      onClick={() => onOpen?.(kpi.id)}
      className="vl-card flex w-full flex-col gap-3 overflow-hidden p-4 text-left"
      style={{ ["--card-accent" as string]: accent }}
    >
      <span
        className="absolute bottom-0 left-0 top-0 w-[3px] rounded-l"
        style={{ background: accent }}
      />

      <div className="flex items-start justify-between gap-2 pl-1">
        <div className="text-[13px] font-semibold tracking-[0.01em] text-[#f2f7fc]">
          {kpi.name}
        </div>
        <span
          className={`shrink-0 rounded px-[7px] py-0.5 text-[10px] font-semibold tracking-[0.04em] ${
            kpi.trend === "up"
              ? "bg-[var(--green-dim)] text-[var(--green)]"
              : kpi.trend === "down"
                ? "bg-[var(--red-dim)] text-[var(--red)]"
                : "bg-[var(--cyan-dim)] text-[var(--cyan)]"
          }`}
        >
          {kpi.trend === "up" ? "▲" : kpi.trend === "down" ? "▼" : "■"} {kpi.trend}
        </span>
      </div>

      <div className="font-display pl-1 text-[30px] font-bold leading-none text-white">
        {formatNumber(kpi.value, digits)}
        <span className="ml-1 text-[14px] font-medium text-[#9eb6d0]">{kpi.unit}</span>
      </div>

      {isShmoo ? (
        <div className="grid grid-cols-2 gap-1.5 pl-1">
          {(shmooMetrics?.length
            ? shmooMetrics
            : SHMOO_CAPABILITIES.map((c) => ({
                id: c.id,
                label: c.label,
                value: Number.NaN,
                unit: "%",
              }))
          ).map((m) => (
            <div
              key={m.id}
              className="rounded border border-[rgba(167,139,250,0.35)] bg-[rgba(167,139,250,0.12)] px-2 py-1.5"
            >
              <div className="text-[9px] font-semibold tracking-[0.04em] text-[#d4c4ff]">
                {m.label}
              </div>
              <div className="font-mono text-[13px] font-semibold text-white">
                {Number.isFinite(m.value) ? (
                  <>
                    {formatNumber(m.value, m.value > 90 && m.unit === "%" ? 2 : 1)}
                    <span className="ml-0.5 text-[10px] font-medium text-[#b8a4e8]">
                      {m.unit}
                    </span>
                  </>
                ) : (
                  <span className="text-[#9eb6d0]">—</span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 pl-1 text-[11px]">
          <Meta label="Target" value={`${formatNumber(kpi.target, digits)}${kpi.unit}`} />
          <Meta label="Baseline" value={`${formatNumber(kpi.baseline, digits)}${kpi.unit}`} />
        </div>
      )}

      {!isShmoo ? (
        <div className="h-[34px] w-full pl-1">
          {chartData.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
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
          ) : null}
        </div>
      ) : null}

      <div className="flex items-center justify-between pl-1 text-[10.5px] text-[#8fa6c0]">
        <span className="uppercase tracking-[0.08em]">{kpi.status.replaceAll("_", " ")}</span>
        <span className="font-mono text-[#c5d8ec]">
          {kpi.timestamp ? formatTime(kpi.timestamp) : "—"}
        </span>
      </div>
    </button>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[6px] border border-[rgba(107,193,242,0.2)] bg-[rgba(107,193,242,0.07)] px-2 py-1.5">
      <div className="text-[9px] font-semibold uppercase tracking-[0.08em] text-[#9ec9ef]">
        {label}
      </div>
      <div className="font-mono text-[11px] font-semibold text-[#f2f7fc]">{value}</div>
    </div>
  );
}
