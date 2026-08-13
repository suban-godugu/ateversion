"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { uploadFloorFile } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

type UploadKind = "auto" | "wafer_image" | "stil" | "stdf" | "log";

/**
 * Header upload control for wafer images, STDF/STIL, and test logs.
 */
export function UploadControl() {
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const canUpload = useAuthStore((s) => s.hasPermission("write:telemetry"));

  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<UploadKind>("auto");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!canUpload) {
    return null;
  }

  const onPick = () => inputRef.current?.click();

  const onFile = async (file: File | null) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const res = await uploadFloorFile(file, kind);
      const detail =
        res.kind === "wafer_image"
          ? `Wafer image ingested · ${res.dies ?? 0} dies · yield ${res.yield_pct ?? "—"}%`
          : `${String(res.kind).toUpperCase()} ingested · ${res.events_accepted ?? 0} events`;
      setMessage(detail);
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["wafer"] });
      void queryClient.invalidateQueries({ queryKey: ["test-events"] });
      void queryClient.invalidateQueries({ queryKey: ["kpis"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        title="Upload wafer image / STDF·STIL / log"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex h-9 w-9 items-center justify-center rounded border border-[var(--line)] bg-[var(--panel)] text-[var(--cyan)] hover:border-[var(--cyan)]"
        aria-label="Upload files"
      >
        <Upload className="h-4 w-4" />
      </button>

      {open ? (
        <div className="absolute right-0 z-40 mt-2 w-[300px] rounded border border-[var(--line)] bg-[var(--panel)] p-3 shadow-lg">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--muted-2)]">
            Upload floor artifacts
          </div>
          <p className="mb-3 text-[11px] leading-relaxed text-[var(--muted)]">
            Wafer map image, STDF/STIL pattern file, or ATE test log. Ingested by the Python
            backend — React only displays results.
          </p>

          <label className="mb-2 flex flex-col gap-1 text-[10px] uppercase tracking-[0.08em] text-[var(--muted-2)]">
            File type
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as UploadKind)}
              className="rounded border border-[var(--line)] bg-[var(--panel-2)] px-2 py-1.5 text-[11.5px] normal-case tracking-normal text-[var(--text)]"
            >
              <option value="auto">Auto-detect</option>
              <option value="wafer_image">Wafer image</option>
              <option value="stil">STIL</option>
              <option value="stdf">STDF</option>
              <option value="log">Test log</option>
            </select>
          </label>

          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept={
              kind === "wafer_image"
                ? ".png,.jpg,.jpeg,.bmp,.webp"
                : kind === "stil"
                  ? ".stil,.stilt,.txt"
                  : kind === "stdf"
                    ? ".stdf,.std,.atr,.txt"
                    : kind === "log"
                      ? ".log,.txt,.csv"
                      : ".png,.jpg,.jpeg,.bmp,.webp,.stil,.stdf,.std,.log,.txt,.csv"
            }
            onChange={(e) => void onFile(e.target.files?.[0] ?? null)}
          />

          <div className="mt-2 flex gap-2">
            <Button type="button" disabled={busy} onClick={onPick}>
              {busy ? "Uploading…" : "Choose file"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Close
            </Button>
          </div>

          {message ? (
            <div className="mt-2 text-[11px] text-[var(--green)]">{message}</div>
          ) : null}
          {error ? <div className="mt-2 text-[11px] text-[var(--red)]">{error}</div> : null}
        </div>
      ) : null}
    </div>
  );
}
