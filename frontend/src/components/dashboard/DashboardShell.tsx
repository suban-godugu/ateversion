"use client";

import { useEffect } from "react";
import { DisconnectedBanner } from "@/components/common/DisconnectedBanner";
import { ErrorState } from "@/components/common/ErrorState";
import { LiveStatusIndicator } from "@/components/common/LiveStatusIndicator";
import { LoadingState } from "@/components/common/LoadingState";
import { VerilumenBrand } from "@/components/branding/VerilumenBrand";
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
    // Lot/wafer from backend only — never inject default tester/site.
    const payload = {
      lotId: summary.active_wafer.lot_id,
      waferId: summary.active_wafer.wafer_id,
      testerId: null as string | null,
      siteId: null as string | null,
    };
    // #region agent log
    const before = useOpsStore.getState();
    const logDbg = (hypothesisId: string, location: string, message: string, data: Record<string, unknown>) => {
      const body = JSON.stringify({
        sessionId: "4c992b",
        runId: "post-fix",
        hypothesisId,
        location,
        message,
        data,
        timestamp: Date.now(),
      });
      fetch("http://127.0.0.1:7849/ingest/4b5f2f89-6889-4769-a476-cb2a233561aa", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "4c992b" },
        body,
      }).catch(() => {});
      fetch("/debug-ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      }).catch(() => {});
    };
    logDbg("A", "DashboardShell.tsx:hydrate-effect", "hydrateFromSummary (no hardcoded ATE-04/1)", {
      before: {
        lotId: before.lotId,
        waferId: before.waferId,
        testerId: before.testerId,
        siteId: before.siteId,
        testerUserSet: before.testerUserSet,
        siteUserSet: before.siteUserSet,
      },
      payload,
    });
    // #endregion
    hydrateFromSummary(payload);
    // #region agent log
    const after = useOpsStore.getState();
    logDbg("B", "DashboardShell.tsx:hydrate-after", "ops state after hydrate", {
      after: {
        lotId: after.lotId,
        waferId: after.waferId,
        testerId: after.testerId,
        siteId: after.siteId,
        testerUserSet: after.testerUserSet,
        siteUserSet: after.siteUserSet,
      },
      keptAll:
        before.testerUserSet &&
        before.testerId === "" &&
        after.testerId === "" &&
        before.siteUserSet &&
        before.siteId === "" &&
        after.siteId === "",
      noHardcodedDefaults: payload.testerId == null && payload.siteId == null,
    });
    // #endregion
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

      <header className="vl-header vl-enter mb-[28px] flex flex-wrap items-end justify-between gap-6">
        <div>
          <VerilumenBrand size="header" />
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <HeaderStats data={summary?.header ?? null} />
          <div className="flex items-end gap-3 border-l border-[var(--line)] pl-4">
            <UploadControl />
            <div className="text-right">
              <div className="vl-label mb-1">Live Connection</div>
              <LiveStatusIndicator />
            </div>
          </div>
        </div>
      </header>

      <div className="vl-enter vl-enter-delay-1">
        <EnterpriseControls />
      </div>

      <section className="vl-surface-deep vl-enter vl-enter-delay-2 mb-[30px] grid grid-cols-1 gap-[26px] p-6 md:grid-cols-[340px_1fr]">
        <WaferMap waferId={wafer?.wafer_id ?? null} />
        <YieldSummary wafer={wafer} />
      </section>

      <div className="vl-section-title mb-3">Optimization Parameters</div>
      <div className="vl-enter vl-enter-delay-3">
        <OptimizationKpiGrid>
          <PredictiveMaintenanceCard />
          <DynamicTestLimits data={summary?.test_limits ?? null} />
        </OptimizationKpiGrid>
      </div>

      <div className="mt-1">
        <TestFloorEventLog />
      </div>

      <footer className="mt-8 flex flex-wrap justify-between gap-2 border-t border-[rgba(107,193,242,0.18)] pt-4 text-[11px] text-[#7f96b0]">
        <span>
          Metrics reflect an ML-assisted test-optimization layer over standard ATE limits and bin
          logic
        </span>
        <span className="font-mono text-[10px] tracking-wide text-[#9ec9ef]">
          {summary?.connection_hint ??
            "Live telemetry · PostgreSQL · Redis · authenticated WebSocket"}
        </span>
      </footer>
    </div>
  );
}
