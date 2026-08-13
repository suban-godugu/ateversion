export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded border border-[var(--line)] bg-[var(--panel)] px-4 py-8 text-center">
      <p className="text-[13px] text-[var(--red)]">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border border-[var(--line-bright)] px-3 py-1 text-[12px] text-[var(--text)] hover:bg-[var(--panel-2)]"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
