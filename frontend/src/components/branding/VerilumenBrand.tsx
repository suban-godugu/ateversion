import Image from "next/image";

type VerilumenBrandProps = {
  /** Compact header mark vs slightly larger login treatment */
  size?: "header" | "auth";
};

/**
 * Compact brand lockup: V emblem + VERILUMEN™ + ATE INTELLIGENCE.
 * Full banner / tagline omitted for header density.
 */
export function VerilumenBrand({ size = "header" }: VerilumenBrandProps) {
  const markH = size === "auth" ? 56 : 48;

  return (
    <div className="flex items-center gap-3">
      <Image
        src="/branding/verilumen-mark.png"
        alt="VERILUMEN"
        width={64}
        height={64}
        className="w-auto object-contain"
        style={{ height: markH, width: markH }}
        priority
      />
      <div className="min-w-0 leading-tight">
        <div
          className={
            size === "auth"
              ? "font-display text-[18px] font-bold uppercase tracking-[0.14em] text-[#e8f2ff]"
              : "font-display text-[15px] font-bold uppercase tracking-[0.14em] text-[#e8f2ff]"
          }
        >
          Verilumen
          <span className="relative -top-2 ml-0.5 text-[8px] tracking-normal text-[var(--cyan)]">
            TM
          </span>
        </div>
        <div
          className={
            size === "auth"
              ? "mt-1 font-display text-[20px] font-semibold uppercase tracking-[0.14em] text-[var(--cyan)]"
              : "mt-0.5 font-display text-[17px] font-semibold uppercase tracking-[0.14em] text-[var(--cyan)]"
          }
        >
          ATE Intelligence
        </div>
      </div>
    </div>
  );
}
