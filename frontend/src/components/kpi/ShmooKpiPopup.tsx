"use client";

import { useEffect, useState } from "react";
import { DetailPopup } from "@/components/common/DetailPopup";
import type { ShmooCapabilityMetric } from "@/components/kpi/OptimizationKpiCard";
import {
  SHMOO_CAPABILITIES,
  SHMOO_VL_BASE,
  shmooCapabilityUrl,
  type ShmooCapabilityId,
} from "@/lib/kpiExternalPages";
import { formatNumber } from "@/lib/utils";

/**
 * Single SHMOO ML-Based Optimization popup with capability tabs
 * (Yield Analysis, Debugging, Binning, Characterization) embedding shmoo-vl.
 */
export function ShmooKpiPopup({
  title,
  onClose,
  metrics,
  initialCapability = "yield",
}: {
  title: string;
  onClose: () => void;
  metrics?: ShmooCapabilityMetric[];
  initialCapability?: ShmooCapabilityId;
}) {
  const [active, setActive] = useState<ShmooCapabilityId>(initialCapability);
  const [loaded, setLoaded] = useState(false);

  const capability =
    SHMOO_CAPABILITIES.find((c) => c.id === active) ?? SHMOO_CAPABILITIES[0];
  const url = shmooCapabilityUrl(capability.view);
  const activeMetric = metrics?.find((m) => m.id === active);

  useEffect(() => {
    setLoaded(false);
  }, [url]);

  return (
    <DetailPopup eyebrow="SHMOO ML" title={title} onClose={onClose} wide>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {SHMOO_CAPABILITIES.map((cap) => {
          const selected = cap.id === active;
          const metric = metrics?.find((m) => m.id === cap.id);
          return (
            <button
              key={cap.id}
              type="button"
              onClick={() => setActive(cap.id)}
              className={`rounded-[6px] border px-2.5 py-1 text-left transition-colors ${
                selected
                  ? "border-[var(--cyan)] bg-[rgba(107,193,242,0.2)] text-white"
                  : "border-[rgba(107,193,242,0.28)] bg-[rgba(107,193,242,0.06)] text-[#9eb6d0] hover:border-[var(--cyan)] hover:text-white"
              }`}
            >
              <div className="text-[11px] font-semibold tracking-[0.02em]">{cap.label}</div>
              <div className="font-mono text-[12px] font-semibold">
                {metric && Number.isFinite(metric.value) ? (
                  <>
                    {formatNumber(
                      metric.value,
                      metric.value > 90 && metric.unit === "%" ? 2 : 1,
                    )}
                    <span className="ml-0.5 text-[10px] opacity-80">{metric.unit}</span>
                  </>
                ) : (
                  "—"
                )}
              </div>
            </button>
          );
        })}
      </div>

      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] text-[var(--muted)]">
          Viewing <span className="font-semibold text-[#c9e6ff]">{capability.label}</span>
          {activeMetric && Number.isFinite(activeMetric.value) ? (
            <>
              {" "}
              ·{" "}
              <span className="font-mono text-[#c9e6ff]">
                {formatNumber(
                  activeMetric.value,
                  activeMetric.value > 90 && activeMetric.unit === "%" ? 2 : 1,
                )}
                {activeMetric.unit}
              </span>
            </>
          ) : null}
        </p>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] font-semibold text-[var(--cyan)] underline-offset-2 hover:underline"
        >
          Open in new tab
        </a>
      </div>

      {!loaded ? (
        <div className="mb-2 text-[10px] text-[var(--muted-2)]">Loading {capability.label}…</div>
      ) : null}

      <div className="overflow-hidden rounded-[8px] border border-[rgba(107,193,242,0.25)] bg-[#0a1220]">
        <iframe
          key={url}
          title={`${title} — ${capability.label}`}
          src={url}
          className="h-[min(70vh,720px)] w-full border-0"
          onLoad={() => setLoaded(true)}
          allow="fullscreen"
          referrerPolicy="no-referrer-when-downgrade"
        />
      </div>

      <p className="mt-2 text-[10px] text-[var(--muted-2)]">
        Full tool:{" "}
        <a
          href={SHMOO_VL_BASE}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--cyan)] hover:underline"
        >
          {SHMOO_VL_BASE}
        </a>
      </p>
    </DetailPopup>
  );
}
