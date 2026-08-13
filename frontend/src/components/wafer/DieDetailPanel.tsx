"use client";

import { DetailPopup } from "@/components/common/DetailPopup";
import { formatTime } from "@/lib/utils";
import type { Die } from "@/types/wafer";
import { DIE_RESULT_COLORS } from "@/types/wafer";

export function DieDetailPanel({
  die,
  onClose,
}: {
  die: Die;
  onClose: () => void;
}) {
  return (
    <DetailPopup eyebrow="Die Analysis" title={die.die_id} onClose={onClose}>
      <div className="mb-4 flex items-center gap-2">
        <span
          className="inline-block h-3 w-3 rounded-[3px]"
          style={{ background: DIE_RESULT_COLORS[die.result] }}
        />
        <span className="font-mono text-[14px] font-semibold uppercase tracking-[0.08em] text-[var(--text)]">
          {die.result}
        </span>
      </div>

      <dl className="grid grid-cols-1 gap-y-2.5 text-[12px] sm:grid-cols-2 sm:gap-x-6">
        <Row label="Die ID" value={die.die_id} />
        <Row label="Wafer" value={die.wafer_id} />
        <Row label="Row" value={String(die.row)} />
        <Row label="Column" value={String(die.column)} />
        <Row label="Result" value={die.result} />
        <Row label="Fail Code" value={die.fail_code ?? "—"} />
        <Row
          label="Test Time"
          value={die.test_time_ms != null ? `${Math.round(die.test_time_ms)} ms` : "—"}
        />
        <Row
          label="Confidence"
          value={die.confidence != null ? `${(die.confidence * 100).toFixed(1)}%` : "—"}
        />
        <Row
          label="Timestamp"
          value={die.timestamp ? formatTime(die.timestamp) : "—"}
        />
      </dl>
    </DetailPopup>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[6px] border border-[var(--line)] bg-[var(--panel-2)] px-3 py-2">
      <dt className="text-[9px] uppercase tracking-[0.08em] text-[var(--muted-2)]">{label}</dt>
      <dd className="mt-0.5 font-mono text-[12px] text-[var(--text)]">{value}</dd>
    </div>
  );
}
