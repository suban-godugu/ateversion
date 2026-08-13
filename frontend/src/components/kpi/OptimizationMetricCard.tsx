"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";
import type { KpiCard } from "@/types/api";
import { formatNumber } from "@/lib/utils";

export function OptimizationMetricCard({ card }: { card: KpiCard }) {
  const chartData = (card.series ?? []).map((v, i) => ({ i, v }));
  const digits = card.unit === "%" && card.value > 90 ? 2 : 1;

  return (
    <div
      className="relative flex flex-col gap-2.5 rounded border border-[var(--line)] bg-[var(--panel)] p-[17px]"
      style={{ ["--card-accent" as string]: card.accent }}
    >
      <span
        className="absolute bottom-0 left-0 top-0 w-0.5 rounded-l"
        style={{ background: card.accent }}
      />
      <div className="flex items-start justify-between">
        <div className="text-[12.5px] font-semibold tracking-[0.01em]">{card.title}</div>
        <span
          className={`rounded-full px-[7px] py-0.5 text-[10px] font-semibold tracking-[0.02em] ${
            card.trend === "up"
              ? "bg-[var(--green-dim)] text-[var(--green)]"
              : "bg-[var(--red-dim)] text-[var(--red)]"
          }`}
        >
          {card.trend === "up" ? "▲" : "▼"} trend
        </span>
      </div>
      <div className="font-display text-[28px] font-bold">
        {formatNumber(card.value, digits)}
        <span className="ml-0.5 text-[14px] font-medium text-[var(--muted)]">{card.unit}</span>
      </div>
      <div className="h-[30px] w-full">
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
              <Area
                type="monotone"
                dataKey="v"
                stroke={card.accent}
                fill={`${card.accent}22`}
                strokeWidth={1.6}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : null}
      </div>
      <div className="text-[11.5px] leading-relaxed text-[var(--muted)]">{card.description}</div>
    </div>
  );
}
