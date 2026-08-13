"use client";

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
    <div className="mt-3 w-full rounded border border-[var(--line)] bg-[var(--panel)] p-3 text-[11.5px]">
      <div className="mb-2 flex items-center justify-between">
        <div className="font-semibold tracking-[0.02em] text-[var(--text)]">Die Analysis</div>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--muted-2)] hover:text-[var(--text)]"
        >
          Close
        </button>
      </div>
      <div className="mb-2 flex items-center gap-2">
        <span
          className="inline-block h-2.5 w-2.5 rounded-[2px]"
          style={{ background: DIE_RESULT_COLORS[die.result] }}
        />
        <span className="font-mono uppercase text-[var(--text)]">{die.result}</span>
      </div>
      <dl className="grid grid-cols-[100px_1fr] gap-y-1.5">
        <dt className="text-[var(--muted-2)]">Die ID</dt>
        <dd className="font-mono text-[var(--text)]">{die.die_id}</dd>
        <dt className="text-[var(--muted-2)]">Row</dt>
        <dd className="font-mono text-[var(--text)]">{die.row}</dd>
        <dt className="text-[var(--muted-2)]">Column</dt>
        <dd className="font-mono text-[var(--text)]">{die.column}</dd>
        <dt className="text-[var(--muted-2)]">Result</dt>
        <dd className="font-mono text-[var(--text)]">{die.result}</dd>
        <dt className="text-[var(--muted-2)]">Fail Code</dt>
        <dd className="font-mono text-[var(--text)]">{die.fail_code ?? "—"}</dd>
        <dt className="text-[var(--muted-2)]">Test Time</dt>
        <dd className="font-mono text-[var(--text)]">
          {die.test_time_ms != null ? `${Math.round(die.test_time_ms)} ms` : "—"}
        </dd>
        <dt className="text-[var(--muted-2)]">Confidence</dt>
        <dd className="font-mono text-[var(--text)]">
          {die.confidence != null ? `${(die.confidence * 100).toFixed(1)}%` : "—"}
        </dd>
        <dt className="text-[var(--muted-2)]">Timestamp</dt>
        <dd className="font-mono text-[var(--text)]">
          {die.timestamp ? formatTime(die.timestamp) : "—"}
        </dd>
        <dt className="text-[var(--muted-2)]">Wafer</dt>
        <dd className="font-mono text-[var(--text)]">{die.wafer_id}</dd>
      </dl>
    </div>
  );
}
