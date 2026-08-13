import type { HeaderStats as HeaderStatsType } from "@/types/api";
import { formatNumber } from "@/lib/utils";

export function HeaderStats({ data }: { data: HeaderStatsType | null }) {
  return (
    <div className="flex flex-wrap gap-[30px]">
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
    <div className="text-right">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--muted-2)]">{label}</div>
      <div className="font-mono text-[21px] font-semibold mt-[3px]" style={{ color }}>
        {value}
      </div>
    </div>
  );
}
