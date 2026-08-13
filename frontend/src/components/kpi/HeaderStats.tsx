import type { HeaderStats as HeaderStatsType } from "@/types/api";
import { formatNumber } from "@/lib/utils";

export function HeaderStats({ data }: { data: HeaderStatsType | null }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Stat label="Lots In Test" value={data ? String(data.lots_in_test) : "—"} />
      <Stat
        label="Test Time Saved (24h)"
        value={data ? `${Math.round(data.test_time_saved_hours)} hrs` : "—"}
        color="var(--green)"
      />
      <Stat
        label="Overall Yield"
        value={data ? `${formatNumber(data.overall_yield_pct)}%` : "—"}
        color="var(--cyan)"
      />
    </div>
  );
}

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="vl-stat text-right">
      <div className="vl-label">{label}</div>
      <div
        className="font-mono mt-1 text-[22px] font-semibold tracking-tight"
        style={{ color: color ?? "var(--text)" }}
      >
        {value}
      </div>
    </div>
  );
}
