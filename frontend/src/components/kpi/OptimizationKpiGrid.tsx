"use client";

import type { ReactNode } from "react";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { ExternalKpiPopup } from "@/components/kpi/ExternalKpiPopup";
import { KpiDetailDrawer } from "@/components/kpi/KpiDetailDrawer";
import { OptimizationKpiCard } from "@/components/kpi/OptimizationKpiCard";
import { getKpiExternalUrl } from "@/lib/kpiExternalPages";
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
  "m_bist_shmoo",
];

const DISPLAY_NAMES: Record<string, string> = {
  m_bist_shmoo: "SHMOO ML Optimization System",
};

function displayName(kpiId: string, fallback: string): string {
  return DISPLAY_NAMES[kpiId] ?? fallback;
}

export function OptimizationKpiGrid({ children }: { children?: ReactNode }) {
  const { kpis, isLoading, isError, refetch } = useKpis();
  const selectedKpiId = useKpiStore((s) => s.selectedKpiId);
  const selectKpi = useKpiStore((s) => s.selectKpi);
  const kpisById = useKpiStore((s) => s.kpisById);

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

  const externalUrl = selectedKpiId ? getKpiExternalUrl(selectedKpiId) : undefined;
  const selectedName = selectedKpiId
    ? displayName(
        selectedKpiId,
        (kpisById[selectedKpiId]?.name) ||
          ordered.find((k) => k.id === selectedKpiId)?.name ||
          "KPI",
      )
    : "KPI";

  return (
    <>
      <div className="mb-[26px] grid grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-3">
        {ordered.map((kpi) => (
          <OptimizationKpiCard
            key={kpi.id}
            kpi={{ ...kpi, name: displayName(kpi.id, kpi.name) }}
            onOpen={selectKpi}
          />
        ))}
        {children}
      </div>
      {selectedKpiId && externalUrl ? (
        <ExternalKpiPopup
          title={selectedName}
          url={externalUrl}
          onClose={() => selectKpi(null)}
        />
      ) : selectedKpiId ? (
        <KpiDetailDrawer kpiId={selectedKpiId} onClose={() => selectKpi(null)} />
      ) : null}
    </>
  );
}
