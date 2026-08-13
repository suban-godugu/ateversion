export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded border border-[var(--line)] bg-[var(--panel)] px-4 py-8 text-center text-[13px] text-[var(--muted)]">
      {message}
    </div>
  );
}
