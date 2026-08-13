import { create } from "zustand";
import type { ShmooMeta, ShmooResults } from "@/types/shmoo";

interface ShmooState {
  sessionId: string | null;
  filename: string | null;
  meta: ShmooMeta | null;
  results: ShmooResults | null;
  plotUrl: string | null;
  setSession: (payload: {
    sessionId: string;
    filename?: string;
    meta: ShmooMeta;
    results: ShmooResults;
    plotUrl: string;
  }) => void;
  clear: () => void;
}

export const useShmooStore = create<ShmooState>((set) => ({
  sessionId: null,
  filename: null,
  meta: null,
  results: null,
  plotUrl: null,
  setSession: ({ sessionId, filename, meta, results, plotUrl }) =>
    set({
      sessionId,
      filename: filename ?? null,
      meta,
      results,
      plotUrl,
    }),
  clear: () =>
    set({
      sessionId: null,
      filename: null,
      meta: null,
      results: null,
      plotUrl: null,
    }),
}));
