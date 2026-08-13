"use client";

import type { ReactNode } from "react";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { KpiDetailDrawer } from "@/components/kpi/KpiDetailDrawer";
import { OptimizationKpiCard } from "@/components/kpi/OptimizationKpiCard";
import { useKpis } from "@/hooks/useKpis";
import { useKpiStore } from "@/stores/kpiStore";

const ORDER = [
  "false_failure_reduction",
  "test_time_reduction",
  "yield_improvement",
  "retest_reduction",
  "escape_prevention",
  "vector_memory_optimization",
  "pattern_count_reduction",
];

export function OptimizationKpiGrid({ children }: { children?: ReactNode }) {
  const { kpis, isLoading, isError, refetch } = useKpis();
  const selectedKpiId = useKpiStore((s) => s.selectedKpiId);
  const selectKpi = useKpiStore((s) => s.selectKpi);

  const ordered = [...kpis].sort((a, b) => {
    const ia = ORDER.indexOf(a.id);
    const ib = ORDER.indexOf(b.id);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  if (isLoading && ordered.length === 0) {
    return <LoadingState label="Loading optimization KPIs…" />;
  }

  if (isError && ordered.length === 0) {
    return (
      <ErrorState
        message="Unable to load KPIs from the API."
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <>
      <div className="mb-[26px] grid grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-3">
        {ordered.map((kpi) => (
          <OptimizationKpiCard key={kpi.id} kpi={kpi} onOpen={selectKpi} />
        ))}
        {children}
      </div>
      {selectedKpiId ? (
        <KpiDetailDrawer kpiId={selectedKpiId} onClose={() => selectKpi(null)} />
      ) : null}
    </>
  );
}
