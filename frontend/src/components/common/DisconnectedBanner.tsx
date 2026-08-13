"use client";

import { useEffect, useState } from "react";
import { useConnectionStore } from "@/stores/connectionStore";

export function DisconnectedBanner() {
  const status = useConnectionStore((s) => s.status);
  const lastError = useConnectionStore((s) => s.lastError);
  const lastMessageAt = useConnectionStore((s) => s.lastMessageAt);
  const [ago, setAgo] = useState<number | null>(null);

  useEffect(() => {
    const tick = () => {
      if (lastMessageAt == null) {
        setAgo(null);
        return;
      }
      setAgo(Math.max(0, Math.floor((Date.now() - lastMessageAt) / 1000)));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [lastMessageAt]);

  if (status === "LIVE") return null;

  const copy =
    status === "RECONNECTING"
      ? "Reconnecting to test-floor event stream…"
      : status === "DEGRADED"
        ? "Event stream degraded — KPI values frozen at last authoritative snapshot."
        : status === "STALE"
          ? "Telemetry stale — KPI / wafer values not refreshed until backend stream resumes."
          : "Event stream offline — showing last synchronized backend state only.";

  return (
    <div className="mb-4 rounded border border-[var(--amber)]/40 bg-[var(--amber-dim)] px-3 py-2 text-[12px] text-[var(--amber)]">
      <span className="font-semibold uppercase tracking-[0.08em]">{status}</span>
      <span className="mx-2 text-[var(--muted-2)]">·</span>
      {copy}
      <span className="ml-2 font-mono text-[11px] text-[var(--muted)]">
        Last telemetry received: {ago == null ? "—" : `${ago}s ago`}
      </span>
      {lastError ? <span className="ml-2 text-[var(--muted)]">({lastError})</span> : null}
    </div>
  );
}
