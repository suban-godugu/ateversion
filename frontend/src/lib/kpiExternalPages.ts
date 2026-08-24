/**
 * External Vercel pages opened when an Optimization KPI card is clicked.
 * Replace placeholder URLs with real deploys via NEXT_PUBLIC_KPI_* env vars.
 */
export const KPI_EXTERNAL_URLS: Record<string, string | undefined> = {
  false_failure_reduction:
    process.env.NEXT_PUBLIC_KPI_FALSE_FAILURE_URL ??
    "https://placeholder-false-failure.vercel.app",
  test_time_reduction:
    process.env.NEXT_PUBLIC_KPI_TEST_TIME_URL ??
    "https://placeholder-test-time.vercel.app",
  yield_improvement:
    process.env.NEXT_PUBLIC_KPI_YIELD_URL ?? "https://placeholder-yield.vercel.app",
  retest_reduction:
    process.env.NEXT_PUBLIC_KPI_RETEST_URL ?? "https://placeholder-retest.vercel.app",
  escape_prevention:
    process.env.NEXT_PUBLIC_KPI_ESCAPE_URL ?? "https://placeholder-escape.vercel.app",
  vector_memory_optimization:
    process.env.NEXT_PUBLIC_KPI_VECTOR_MEMORY_URL ??
    "https://placeholder-vector-memory.vercel.app",
  pattern_count_reduction:
    process.env.NEXT_PUBLIC_KPI_PATTERN_COUNT_URL ??
    "https://placeholder-pattern-count.vercel.app",
  m_bist_shmoo:
    process.env.NEXT_PUBLIC_KPI_M_BIST_SHMOO_URL ??
    "https://placeholder-m-bist-shmoo.vercel.app",
};

export function getKpiExternalUrl(kpiId: string): string | undefined {
  const url = KPI_EXTERNAL_URLS[kpiId]?.trim();
  return url || undefined;
}

export function isPlaceholderKpiUrl(url: string): boolean {
  return /placeholder-/i.test(url) || /example\.com/i.test(url);
}
