import type { WaferDetail } from "@/types/api";
import { formatNumber } from "@/lib/utils";

export function YieldSummary({ wafer }: { wafer: WaferDetail | null }) {
  const bins = wafer?.bin_counts;
  return (
    <div className="flex flex-col justify-center gap-3.5">
      <div className="flex flex-wrap gap-5 text-[11px] uppercase tracking-[0.1em] text-[var(--muted-2)]">
        <span>
          Lot{" "}
          <b className="ml-1 font-mono text-[13px] normal-case tracking-normal text-[var(--text)]">
            {wafer?.lot_id ?? "—"}
          </b>
        </span>
        <span>
          Wafer{" "}
          <b className="ml-1 font-mono text-[13px] normal-case tracking-normal text-[var(--text)]">
            {wafer?.wafer_id ?? "—"}
          </b>
        </span>
      </div>
      <div className="font-display text-[56px] font-bold leading-none">
        <span>{wafer ? formatNumber(wafer.yield_pct) : "—"}</span>
        <span className="ml-1 text-[24px] font-medium text-[var(--muted)]">% yield</span>
      </div>
      <p className="max-w-[560px] text-[13.5px] leading-relaxed text-[var(--muted)]">
        Per-die bin classification, re-scored continuously against test-correlation history.
        Marginal fails are re-evaluated before being counted against yield; confirmed escapes
        trigger an immediate limit review on the affected site.
      </p>
      <div className="mt-1 flex flex-wrap gap-[22px]">
        <Bin swatch="var(--green)" label="Pass" value={bins?.pass} />
        <Bin swatch="var(--amber)" label="Retest" value={bins?.retest} />
        <Bin swatch="var(--red)" label="Fail" value={bins?.fail} />
        <Bin swatch="var(--cyan)" label="Reclassified" value={bins?.reclass} />
      </div>
    </div>
  );
}

function Bin({
  swatch,
  label,
  value,
}: {
  swatch: string;
  label: string;
  value?: number;
}) {
  return (
    <span className="flex items-center gap-[7px] text-[12px] text-[var(--muted)]">
      <i className="inline-block h2.5 w-2.5 rounded-[2px]" style={{ background: swatch, width: 10, height: 10 }} />
      {label}{" "}
      <b className="ml-0.5 font-mono text-[var(--text)]">{value ?? "—"}</b>
    </span>
  );
}
