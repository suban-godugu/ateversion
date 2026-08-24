"use client";

import { useState } from "react";
import { DetailPopup } from "@/components/common/DetailPopup";
import { isPlaceholderKpiUrl } from "@/lib/kpiExternalPages";

/**
 * Centered popup that embeds a separately deployed Vercel KPI page.
 */
export function ExternalKpiPopup({
  title,
  url,
  onClose,
}: {
  title: string;
  url: string;
  onClose: () => void;
}) {
  const [loaded, setLoaded] = useState(false);
  const placeholder = isPlaceholderKpiUrl(url);

  return (
    <DetailPopup eyebrow="External KPI page" title={title} onClose={onClose} wide>
      {placeholder ? (
        <div className="mb-3 rounded border border-[var(--amber)]/40 bg-[var(--amber-dim)] px-3 py-2 text-[11px] leading-relaxed text-[var(--amber)]">
          Placeholder URL — replace with your real Vercel deploy via{" "}
          <span className="font-mono">NEXT_PUBLIC_KPI_*</span> env vars.
        </div>
      ) : null}

      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] font-semibold text-[var(--cyan)] underline-offset-2 hover:underline"
        >
          Open in new tab
        </a>
        {!loaded && !placeholder ? (
          <span className="text-[10px] text-[var(--muted-2)]">Loading page…</span>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-[8px] border border-[rgba(107,193,242,0.25)] bg-[#0a1220]">
        <iframe
          title={title}
          src={url}
          className="h-[min(70vh,720px)] w-full border-0"
          onLoad={() => setLoaded(true)}
          allow="fullscreen"
          referrerPolicy="no-referrer-when-downgrade"
        />
      </div>
    </DetailPopup>
  );
}
