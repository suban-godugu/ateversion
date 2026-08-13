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
      <div className="pointer-events-none fixed inset-0 bg-black/45" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`vl-popup pointer-events-auto flex max-h-[min(90vh,860px)] w-full flex-col overflow-hidden ${
          wide ? "max-w-[720px]" : "max-w-[560px]"
        }`}
      >
        <header className="flex shrink-0 items-start justify-between border-b border-[rgba(107,193,242,0.28)] px-5 py-4">
          <div>
            {eyebrow ? <div className="vl-popup-label">{eyebrow}</div> : null}
            <h2 className="font-display mt-1 text-[22px] font-semibold text-white">
              {title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[6px] border border-[rgba(107,193,242,0.45)] bg-[rgba(107,193,242,0.12)] px-2.5 py-1 text-[11px] font-semibold text-[#c9e6ff] transition-colors hover:border-[var(--cyan)] hover:text-white"
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
