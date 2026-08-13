export function LoadingState({ label = "Loading floor telemetry…" }: { label?: string }) {
  return (
    <div className="flex min-h-[240px] items-center justify-center rounded border border-[var(--line)] bg-[var(--panel)] text-[13px] text-[var(--muted)]">
      {label}
    </div>
  );
}
