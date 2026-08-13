"use client";

import { formatTime } from "@/lib/utils";
import type { TestEvent } from "@/types/events";
import { SEVERITY_STYLES } from "@/types/events";

interface Props {
  event: TestEvent | null;
  onClose: () => void;
  onAcknowledge: (eventId: string) => void;
  acknowledging?: boolean;
}

export function EventDetails({ event, onClose, onAcknowledge, acknowledging }: Props) {
  if (!event) {
    return (
      <div className="flex h-full min-h-[220px] flex-col items-center justify-center rounded border border-dashed border-[var(--line)] bg-[var(--panel-2)] px-4 text-center text-[11.5px] text-[var(--muted)]">
        Select an event to inspect payload, lineage, and acknowledge.
      </div>
    );
  }

  const style = SEVERITY_STYLES[event.severity];

  return (
    <div className="flex h-full min-h-[220px] flex-col rounded border border-[var(--line)] bg-[var(--panel-2)] p-3.5">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--muted-2)]">
            Event detail
          </div>
          <div className="mt-1 font-mono text-[11px] text-[var(--muted)]">{event.event_id}</div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-[11px] text-[var(--muted-2)] hover:text-[var(--text)]"
        >
          Close
        </button>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span
          className="rounded px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.04em]"
          style={{ color: style.fg, background: style.bg }}
        >
          {event.severity}
        </span>
        <span className="rounded bg-[var(--line)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--muted)]">
          {event.event_type}
        </span>
        <span className="font-mono text-[10px] text-[var(--muted-2)]">
          seq {event.sequence_number}
        </span>
      </div>

      <p className="mb-3 text-[12px] leading-relaxed text-[var(--text)]">{event.message}</p>

      <dl className="mb-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
        <Field label="Timestamp" value={formatTime(event.timestamp)} />
        <Field label="Source" value={event.source} />
        <Field label="Tester" value={event.tester_id} />
        <Field label="Site" value={event.site_id} />
        <Field label="Lot" value={event.lot_id} />
        <Field label="Wafer" value={event.wafer_id} />
        <Field label="Die" value={event.die_id} />
        <Field
          label="Ack"
          value={
            event.acknowledged
              ? `${event.acknowledged_by ?? "yes"}${
                  event.acknowledged_at ? ` · ${formatTime(event.acknowledged_at)}` : ""
                }`
              : "open"
          }
        />
      </dl>

      <div className="mb-3 flex-1 overflow-auto rounded border border-[var(--line)] bg-[var(--bg)] p-2">
        <div className="mb-1 text-[10px] uppercase tracking-[0.08em] text-[var(--muted-2)]">
          Metadata
        </div>
        <pre className="whitespace-pre-wrap break-all font-mono text-[10px] leading-relaxed text-[var(--muted)]">
          {JSON.stringify(event.metadata ?? {}, null, 2)}
        </pre>
      </div>

      <button
        type="button"
        disabled={event.acknowledged || acknowledging}
        onClick={() => onAcknowledge(event.event_id)}
        className="rounded border border-[var(--cyan)] px-3 py-1.5 text-[11px] font-semibold text-[var(--cyan)] disabled:opacity-40"
      >
        {event.acknowledged ? "Acknowledged" : acknowledging ? "Acknowledging…" : "Acknowledge"}
      </button>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-[9.5px] uppercase tracking-[0.08em] text-[var(--muted-2)]">{label}</dt>
      <dd className="mt-0.5 font-mono text-[11px] text-[var(--text)]">{value ?? "—"}</dd>
    </div>
  );
}
