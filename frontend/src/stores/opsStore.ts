import { create } from "zustand";

export type StreamMode = "LIVE" | "PAUSED";

interface OpsState {
  lotId: string;
  waferId: string;
  testerId: string;
  siteId: string;
  since: string;
  until: string;
  streamMode: StreamMode;
  reconnectNonce: number;
  /** Once user edits tester/site (including All=""), hydrate must not overwrite. */
  testerUserSet: boolean;
  siteUserSet: boolean;
  setLotId: (v: string) => void;
  setWaferId: (v: string) => void;
  setTesterId: (v: string) => void;
  setSiteId: (v: string) => void;
  setSince: (v: string) => void;
  setUntil: (v: string) => void;
  setStreamMode: (v: StreamMode) => void;
  toggleStreamMode: () => void;
  requestReconnect: () => void;
  hydrateFromSummary: (opts: {
    lotId?: string | null;
    waferId?: string | null;
    testerId?: string | null;
    siteId?: string | null;
  }) => void;
}

export const useOpsStore = create<OpsState>((set, get) => ({
  lotId: "",
  waferId: "",
  testerId: "",
  siteId: "",
  since: "",
  until: "",
  streamMode: "LIVE",
  reconnectNonce: 0,
  testerUserSet: false,
  siteUserSet: false,
  setLotId: (lotId) => set({ lotId }),
  setWaferId: (waferId) => set({ waferId }),
  setTesterId: (testerId) => set({ testerId, testerUserSet: true }),
  setSiteId: (siteId) => set({ siteId, siteUserSet: true }),
  setSince: (since) => set({ since }),
  setUntil: (until) => set({ until }),
  setStreamMode: (streamMode) => set({ streamMode }),
  toggleStreamMode: () =>
    set({ streamMode: get().streamMode === "LIVE" ? "PAUSED" : "LIVE" }),
  requestReconnect: () => set({ reconnectNonce: get().reconnectNonce + 1 }),
  hydrateFromSummary: ({ lotId, waferId, testerId, siteId }) => {
    const cur = get();
    const next = {
      lotId: cur.lotId || lotId || "",
      waferId: cur.waferId || waferId || "",
      // Respect user choice of All ("") — do not treat empty as unset after user edit
      testerId: cur.testerUserSet ? cur.testerId : cur.testerId || testerId || "",
      siteId: cur.siteUserSet ? cur.siteId : cur.siteId || siteId || "",
    };
    // #region agent log
    {
      const payload = {
        sessionId: "4c992b",
        runId: "post-fix",
        hypothesisId: "C",
        location: "opsStore.ts:hydrateFromSummary",
        message: "hydrate merge with user-set locks",
        data: {
          cur: {
            lotId: cur.lotId,
            waferId: cur.waferId,
            testerId: cur.testerId,
            siteId: cur.siteId,
            testerUserSet: cur.testerUserSet,
            siteUserSet: cur.siteUserSet,
          },
          incoming: { lotId, waferId, testerId, siteId },
          next,
          respectedAll:
            cur.testerUserSet && cur.testerId === "" && next.testerId === "",
        },
        timestamp: Date.now(),
      };
      const body = JSON.stringify(payload);
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
    }
    // #endregion
    set(next);
  },
}));
