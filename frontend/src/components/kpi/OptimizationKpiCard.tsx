"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { formatNumber, formatTime } from "@/lib/utils";
import type { Kpi } from "@/types/kpi";

export interface OptimizationKpiCardProps {
  kpi: Kpi;
  onOpen?: (kpiId: string) => void;
}

export function OptimizationKpiCard({ kpi, onOpen }: OptimizationKpiCardProps) {
  const accent = kpi.accent ?? "#6EE7A8";
  const chartData = (kpi.history ?? []).map((p, i) => ({ i, v: p.value }));
  const digits = kpi.unit === "%" && kpi.value > 90 ? 2 : 1;

  return (
    <button
      type="button"
      onClick={() => onOpen?.(kpi.id)}
      className="relative flex w-full flex-col gap-2.5 rounded border border-[var(--line)] bg-[var(--panel)] p-[17px] text-left transition-colors hover:border-[var(--line-bright)]"
      style={{ ["--card-accent" as string]: accent }}
    >
      <span className="absolute bottom-0 left-0 top-0 w-0.5 rounded-l" style={{ background: accent }} />

      <div className="flex items-start justify-between gap-2">
        <div className="text-[12.5px] font-semibold tracking-[0.01em]">{kpi.name}</div>
        <span
          className={`shrink-0 rounded-full px-[7px] py-0.5 text-[10px] font-semibold tracking-[0.02em] ${
            kpi.trend === "up"
              ? "bg-[var(--green-dim)] text-[var(--green)]"
              : kpi.trend === "down"
                ? "bg-[var(--red-dim)] text-[var(--red)]"
                : "bg-[var(--cyan-dim)] text-[var(--cyan)]"
          }`}
        >
          {kpi.trend === "up" ? "▲" : kpi.trend === "down" ? "▼" : "■"} trend
        </span>
      </div>

      <div className="font-display text-[28px] font-bold">
        {formatNumber(kpi.value, digits)}
        <span className="ml-0.5 text-[14px] font-medium text-[var(--muted)]">{kpi.unit}</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <Meta label="Target" value={`${formatNumber(kpi.target, digits)}${kpi.unit}`} />
        <Meta label="Baseline" value={`${formatNumber(kpi.baseline, digits)}${kpi.unit}`} />
      </div>

      <div className="h-[30px] w-full">
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
              <Area
                type="monotone"
                dataKey="v"
                stroke={accent}
                fill={`${accent}22`}
                strokeWidth={1.6}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : null}
      </div>

      <div className="flex items-center justify-between text-[10.5px] text-[var(--muted-2)]">
        <span className="uppercase tracking-[0.06em]">{kpi.status.replaceAll("_", " ")}</span>
        <span className="font-mono">
          {kpi.timestamp ? formatTime(kpi.timestamp) : "—"}
        </span>
      </div>
    </button>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--line)] bg-[var(--panel-2)] px-2 py-1">
      <div className="text-[9px] uppercase tracking-[0.08em] text-[var(--muted-2)]">{label}</div>
      <div className="font-mono text-[11px] text-[var(--text)]">{value}</div>
    </div>
  );
}
