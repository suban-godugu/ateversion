import type {
  DashboardSummary,
  DieOut,
  TestLimitOut,
  TestLimitsOut,
} from "@/types/api";
import type {
  EventFilterOptions,
  EventFiltersState,
  TestEvent,
  TestEventsListOut,
} from "@/types/events";
import type { Kpi, KpiDetail, KpiHistoryResponse } from "@/types/kpi";
import type { MaintenanceList, MaintenanceTesterDetail } from "@/types/maintenance";

import { useAuthStore } from "@/stores/authStore";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (typeof window !== "undefined" ? `${window.location.origin}/api` : "http://127.0.0.1:8000/api");

function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function requestJson<T>(path: string, init?: RequestInit, retries = 2): Promise<T> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        cache: "no-store",
        headers: {
          Accept: "application/json",
          ...authHeaders(),
          ...(init?.body ? { "Content-Type": "application/json" } : {}),
          ...(init?.headers ?? {}),
        },
        ...init,
      });
      if (res.status === 401) {
        useAuthStore.getState().clearSession();
        throw new Error(`API ${path} unauthorized`);
      }
      if (res.status === 429 && attempt < retries) {
        await sleep(300 * 2 ** attempt);
        continue;
      }
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(`API ${path} failed: ${res.status}${detail ? ` ${detail}` : ""}`);
      }
      return res.json() as Promise<T>;
    } catch (err) {
      lastErr = err;
      if (attempt < retries && !(err instanceof Error && err.message.includes("unauthorized"))) {
        await sleep(250 * 2 ** attempt);
        continue;
      }
      throw err;
    }
  }
  throw lastErr;
}

async function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path);
}

export async function login(username: string, password: string) {
  // Never attach a stale Bearer token to login (avoids 401 session wipe races).
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Login failed: ${res.status}${detail ? ` ${detail}` : ""}`);
  }
  return res.json() as Promise<{
    access_token: string;
    token_type: string;
    role: string;
    username: string;
    user_id: string;
    expires_in_minutes: number;
  }>;
}

export function fetchMe() {
  return getJson<{
    user_id: string;
    username: string;
    full_name: string;
    role: string;
    permissions: string[];
  }>("/auth/me");
}

export function fetchReady() {
  return getJson<{
    status: string;
    database: boolean;
    redis: boolean;
    websocket_clients: number;
  }>("/ready");
}

export function fetchDashboardSummary() {
  return getJson<DashboardSummary>("/dashboard/summary");
}

export function fetchWafer(waferId: string) {
  return getJson<import("@/types/api").WaferDetail>(
    `/wafers/${encodeURIComponent(waferId)}`,
  );
}

export function fetchWaferDies(waferId: string) {
  return getJson<DieOut[]>(`/wafers/${encodeURIComponent(waferId)}/dies`);
}

export function fetchKpis() {
  return getJson<{ kpis: Kpi[] }>("/kpis");
}

export function fetchKpi(kpiId: string) {
  return getJson<KpiDetail>(`/kpis/${encodeURIComponent(kpiId)}`);
}

export function fetchKpiHistory(kpiId: string, limit = 48) {
  return getJson<KpiHistoryResponse>(
    `/kpis/${encodeURIComponent(kpiId)}/history?limit=${limit}`,
  );
}

export function fetchTestEvents(filters: Partial<EventFiltersState> & { limit?: number; offset?: number } = {}) {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.tester_id) params.set("tester_id", filters.tester_id);
  if (filters.site_id) params.set("site_id", filters.site_id);
  if (filters.lot_id) params.set("lot_id", filters.lot_id);
  if (filters.wafer_id) params.set("wafer_id", filters.wafer_id);
  if (filters.since) params.set("since", filters.since);
  if (filters.until) params.set("until", filters.until);
  if (filters.acknowledged) params.set("acknowledged", filters.acknowledged);
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.offset) params.set("offset", String(filters.offset));
  for (const sev of filters.severity ?? []) {
    params.append("severity", sev);
  }
  const qs = params.toString();
  return getJson<TestEventsListOut>(`/events${qs ? `?${qs}` : ""}`);
}

export function fetchEventFilterOptions() {
  return getJson<EventFilterOptions>("/events/filters");
}

export function fetchTestEvent(eventId: string) {
  return getJson<TestEvent>(`/events/${encodeURIComponent(eventId)}`);
}

export function acknowledgeTestEvent(
  eventId: string,
  body: { actor?: string; comment?: string } = {},
) {
  return requestJson<TestEvent>(`/events/${encodeURIComponent(eventId)}/acknowledge`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchMaintenance() {
  return getJson<MaintenanceList>("/maintenance");
}

export function fetchMaintenanceTester(testerId: string) {
  return getJson<MaintenanceTesterDetail>(`/maintenance/${encodeURIComponent(testerId)}`);
}

export function postMaintenancePredict(body: {
  tester_id?: string;
  component?: string;
  publish?: boolean;
}) {
  return requestJson<{ predictions: MaintenanceList["assets"] }>("/maintenance/predict", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchTestLimits() {
  return getJson<TestLimitsOut>("/test-limits");
}

export function fetchTestLimit(limitId: string) {
  return getJson<TestLimitOut>(`/test-limits/${encodeURIComponent(limitId)}`);
}

export function recommendTestLimit(
  limitId: string,
  body: { samples?: number[]; lsl?: number; usl?: number; target_cpk?: number; actor?: string } = {},
) {
  return requestJson<TestLimitOut>(`/test-limits/${encodeURIComponent(limitId)}/recommend`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function approveTestLimit(limitId: string, body: { actor?: string; comment?: string } = {}) {
  return requestJson<TestLimitOut>(`/test-limits/${encodeURIComponent(limitId)}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function rejectTestLimit(limitId: string, body: { actor?: string; comment?: string } = {}) {
  return requestJson<TestLimitOut>(`/test-limits/${encodeURIComponent(limitId)}/reject`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function rollbackTestLimit(limitId: string, body: { actor?: string; comment?: string } = {}) {
  return requestJson<TestLimitOut>(`/test-limits/${encodeURIComponent(limitId)}/rollback`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchHealth() {
  return getJson<{ status: string; database: boolean; redis: boolean }>("/health");
}
