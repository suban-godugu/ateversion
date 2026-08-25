"use client";

import type { ReactNode } from "react";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { ExternalKpiPopup } from "@/components/kpi/ExternalKpiPopup";
import { KpiDetailDrawer } from "@/components/kpi/KpiDetailDrawer";
import { OptimizationKpiCard } from "@/components/kpi/OptimizationKpiCard";
import { ShmooKpiPopup } from "@/components/kpi/ShmooKpiPopup";
import { getKpiExternalUrl, SHMOO_CAPABILITIES } from "@/lib/kpiExternalPages";
import { useKpis } from "@/hooks/useKpis";
import { useKpiStore } from "@/stores/kpiStore";
import { useShmooStore } from "@/stores/shmooStore";

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

/** Legacy child KPI ids — hide if still present in an older DB. */
const HIDDEN_KPI_IDS = new Set([
  "shmoo_yield_analysis",
  "shmoo_debugging",
  "shmoo_binning",
  "shmoo_characterization",
]);

const DISPLAY_NAMES: Record<string, string> = {
  m_bist_shmoo: "SHMOO ML-Based Optimization",
};

function displayName(kpiId: string, fallback: string): string {
  return DISPLAY_NAMES[kpiId] ?? fallback;
}

export function OptimizationKpiGrid({ children }: { children?: ReactNode }) {
  const { kpis, isLoading, isError, refetch } = useKpis();
  const selectedKpiId = useKpiStore((s) => s.selectedKpiId);
  const selectKpi = useKpiStore((s) => s.selectKpi);
  const kpisById = useKpiStore((s) => s.kpisById);
  const plotUrls = useShmooStore((s) => s.plotUrls);
  const plotUrl = useShmooStore((s) => s.plotUrl);

  const ordered = [...kpis]
    .filter((k) => !HIDDEN_KPI_IDS.has(k.id))
    .sort((a, b) => {
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
        kpisById[selectedKpiId]?.name ||
          ordered.find((k) => k.id === selectedKpiId)?.name ||
          "KPI",
      )
    : "KPI";

  const shmooMetrics = SHMOO_CAPABILITIES.map((cap) => {
    const metric = kpisById[cap.metricKpiId] ?? kpis.find((k) => k.id === cap.metricKpiId);
    return {
      id: cap.id,
      label: cap.label,
      value: metric?.value ?? Number.NaN,
      unit: metric?.unit ?? "%",
    };
  });

  const shmooPlots = [
    {
      key: "yield",
      label: "Yield",
      src: plotUrls.yield,
    },
    {
      key: "debug",
      label: "Debug",
      src: plotUrls.debug,
    },
    {
      key: "character",
      label: "Character",
      src: plotUrls.character ?? plotUrl,
    },
  ];

  return (
    <>
      <div className="mb-[26px] grid grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-3">
        {ordered.map((kpi) => (
          <OptimizationKpiCard
            key={kpi.id}
            kpi={{ ...kpi, name: displayName(kpi.id, kpi.name) }}
            onOpen={selectKpi}
            shmooMetrics={kpi.id === "m_bist_shmoo" ? shmooMetrics : undefined}
            shmooPlots={kpi.id === "m_bist_shmoo" ? shmooPlots : undefined}
          />
        ))}
        {children}
      </div>
      {selectedKpiId === "m_bist_shmoo" ? (
        <ShmooKpiPopup
          title={selectedName}
          metrics={shmooMetrics}
          onClose={() => selectKpi(null)}
        />
      ) : selectedKpiId && externalUrl ? (
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
