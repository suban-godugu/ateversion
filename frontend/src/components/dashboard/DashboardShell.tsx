"use client";

import { useEffect } from "react";
import { DisconnectedBanner } from "@/components/common/DisconnectedBanner";
import { ErrorState } from "@/components/common/ErrorState";
import { LiveStatusIndicator } from "@/components/common/LiveStatusIndicator";
import { LoadingState } from "@/components/common/LoadingState";
import { EnterpriseControls } from "@/components/dashboard/EnterpriseControls";
import { TestFloorEventLog } from "@/components/events/TestFloorEventLog";
import { HeaderStats } from "@/components/kpi/HeaderStats";
import { OptimizationKpiGrid } from "@/components/kpi/OptimizationKpiGrid";
import { DynamicTestLimits } from "@/components/limits/DynamicTestLimits";
import { PredictiveMaintenanceCard } from "@/components/maintenance/PredictiveMaintenanceCard";
import { UploadControl } from "@/components/uploads/UploadControl";
import { WaferMap } from "@/components/wafer/WaferMap";
import { YieldSummary } from "@/components/wafer/YieldSummary";
import { useQuery } from "@tanstack/react-query";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useWaferRealtime } from "@/hooks/useWaferRealtime";
import { fetchWafer } from "@/services/api";
import { useOpsStore } from "@/stores/opsStore";

export function DashboardShell() {
  const { summary, isLoading, isError, refetch } = useDashboardData();
  const selectedWaferId = useOpsStore((s) => s.waferId);
  const hydrateFromSummary = useOpsStore((s) => s.hydrateFromSummary);

  useEffect(() => {
    if (!summary?.active_wafer) return;
    hydrateFromSummary({
      lotId: summary.active_wafer.lot_id,
      waferId: summary.active_wafer.wafer_id,
      testerId: "ATE-04",
      siteId: "1",
    });
  }, [summary, hydrateFromSummary]);

  const waferId = selectedWaferId || summary?.active_wafer?.wafer_id || null;
  useWaferRealtime(waferId, true);

  const waferQuery = useQuery({
    queryKey: ["wafer", waferId, "detail"],
    queryFn: () => fetchWafer(waferId!),
    enabled: Boolean(waferId),
    staleTime: 8_000,
  });

  if (isLoading && !summary) {
    return (
      <div className="mx-auto max-w-[1400px] px-7 pb-[90px] pt-[30px]">
        <LoadingState />
      </div>
    );
  }

  if (isError && !summary) {
    return (
      <div className="mx-auto max-w-[1400px] px-7 pb-[90px] pt-[30px]">
        <ErrorState
          message="Unable to load dashboard summary from the API."
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  const wafer = waferQuery.data ?? summary?.active_wafer ?? null;

  return (
    <div className="mx-auto max-w-[1400px] px-7 pb-[90px] pt-[30px]">
      <DisconnectedBanner />

      <header className="mb-[26px] flex flex-wrap items-end justify-between gap-6 border-b border-[var(--line)] pb-5">
        <div>
          <h1 className="font-display m-0 text-[34px] font-bold uppercase tracking-[0.06em] text-[var(--text)]">
            Verilumen
          </h1>
          <div className="mt-1.5 text-[16px] font-medium tracking-[0.04em] text-[var(--muted)]">
            ATE intelligence
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-6">
          <HeaderStats data={summary?.header ?? null} />
          <div className="flex items-end gap-3">
            <UploadControl />
            <div className="text-right">
              <div className="mb-1 text-[10px] uppercase tracking-[0.1em] text-[var(--muted-2)]">
                Live Connection
              </div>
              <LiveStatusIndicator />
            </div>
          </div>
        </div>
      </header>

      <EnterpriseControls />

      <section className="mb-[30px] grid grid-cols-1 gap-[26px] rounded border border-[var(--line)] bg-[var(--panel-2)] p-6 md:grid-cols-[340px_1fr]">
        <WaferMap waferId={wafer?.wafer_id ?? null} />
        <YieldSummary wafer={wafer} />
      </section>

      <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--muted-2)]">
        Optimization Parameters
      </div>
      <OptimizationKpiGrid>
        <PredictiveMaintenanceCard />
        <DynamicTestLimits data={summary?.test_limits ?? null} />
      </OptimizationKpiGrid>

      <TestFloorEventLog />

      <footer className="mt-6 flex flex-wrap justify-between gap-2 border-t border-[var(--line)] pt-4 text-[11px] text-[var(--muted-2)]">
        <span>
          Metrics reflect an ML-assisted test-optimization layer over standard ATE limits and bin
          logic
        </span>
        <span>
          {summary?.connection_hint ??
            "Live telemetry · PostgreSQL projections · Redis fan-out · authenticated WebSocket"}
        </span>
      </footer>
    </div>
  );
}
