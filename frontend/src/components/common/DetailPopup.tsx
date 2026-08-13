"use client";

import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Centered detail popup portaled to body.
 * Does not lock page scroll; Esc / Close dismisses.
 */
export function DetailPopup({
  title,
  eyebrow,
  onClose,
  children,
  wide,
}: {
  title: string;
  eyebrow?: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!mounted) return null;

  return createPortal(
    <div
      className="pointer-events-none fixed inset-0 z-[80] flex items-start justify-center p-4 pt-[8vh] sm:p-6 sm:pt-[10vh]"
      role="presentation"
    >
      <div className="pointer-events-none fixed inset-0 bg-black/50" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`pointer-events-auto flex max-h-[min(90vh,860px)] w-full flex-col overflow-hidden rounded-[8px] border border-[var(--line)] shadow-[0_24px_80px_rgba(0,0,0,0.55)] ${
          wide ? "max-w-[720px]" : "max-w-[560px]"
        }`}
        style={{
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.03), transparent 36%), var(--panel)",
        }}
      >
        <header className="flex shrink-0 items-start justify-between border-b border-[var(--line)] px-5 py-4">
          <div>
            {eyebrow ? <div className="vl-label">{eyebrow}</div> : null}
            <h2 className="font-display mt-1 text-[20px] font-semibold text-[var(--text)]">
              {title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[6px] border border-[var(--line-bright)] px-2.5 py-1 text-[11px] text-[var(--muted)] transition-colors hover:border-[rgba(107,193,242,0.45)] hover:text-[var(--text)]"
          >
            Close
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
