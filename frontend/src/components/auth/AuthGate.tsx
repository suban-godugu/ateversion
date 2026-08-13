"use client";

import { useEffect, useState } from "react";
import { fetchMe, login } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";
import type { AppRole } from "@/stores/authStore";

/**
 * Ensures a JWT session before rendering the dashboard.
 * Demo defaults can be overridden via NEXT_PUBLIC_DEMO_USER / NEXT_PUBLIC_DEMO_PASSWORD.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.accessToken);
  const setSession = useAuthStore((s) => s.setSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  const [username, setUsername] = useState(
    process.env.NEXT_PUBLIC_DEMO_USER ?? "viewer",
  );
  const [password, setPassword] = useState(
    process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? "viewer123",
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true));
    setHydrated(useAuthStore.persist.hasHydrated());
    return unsub;
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    (async () => {
      const current = useAuthStore.getState().accessToken;
      if (!current) {
        // Attempt silent demo login for local ops tooling
        try {
          setBusy(true);
          const res = await login(username, password);
          if (cancelled) return;
          setSession({
            accessToken: res.access_token,
            username: res.username,
            role: res.role as AppRole,
          });
          const me = await fetchMe();
          if (!cancelled) {
            setSession({
              accessToken: res.access_token,
              username: me.username,
              role: me.role as AppRole,
              permissions: me.permissions,
            });
            setReady(true);
          }
        } catch {
          if (!cancelled) setReady(false);
        } finally {
          if (!cancelled) setBusy(false);
        }
        return;
      }
      try {
        const me = await fetchMe();
        if (!cancelled) {
          setSession({
            accessToken: current,
            username: me.username,
            role: me.role as AppRole,
            permissions: me.permissions,
          });
          setReady(true);
        }
      } catch {
        if (!cancelled) {
          clearSession();
          setReady(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated]);

  if (ready && token) return <>{children}</>;

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="font-display mb-1 text-2xl font-bold uppercase tracking-[0.06em]">
        Veri<span className="text-[var(--green)]">lumen</span>
      </h1>
      <div className="mb-2 text-[13px] font-medium tracking-[0.04em] text-[var(--muted)]">
        ATE intelligence
      </div>
      <p className="mb-6 text-[12px] text-[var(--muted)]">
        Sign in with an authorized engineering role. Unauthorized API / WebSocket
        access is rejected.
      </p>
      <form
        className="flex flex-col gap-3 rounded border border-[var(--line)] bg-[var(--panel)] p-4"
        onSubmit={(e) => {
          e.preventDefault();
          void (async () => {
            setBusy(true);
            setError(null);
            try {
              const res = await login(username, password);
              setSession({
                accessToken: res.access_token,
                username: res.username,
                role: res.role as AppRole,
              });
              const me = await fetchMe();
              setSession({
                accessToken: res.access_token,
                username: me.username,
                role: me.role as AppRole,
                permissions: me.permissions,
              });
              setReady(true);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Login failed");
            } finally {
              setBusy(false);
            }
          })();
        }}
      >
        <label className="text-[10px] uppercase tracking-[0.08em] text-[var(--muted-2)]">
          Username
          <input
            className="mt-1 w-full rounded border border-[var(--line)] bg-[var(--panel-2)] px-2 py-1.5 text-[12px] text-[var(--text)]"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
        </label>
        <label className="text-[10px] uppercase tracking-[0.08em] text-[var(--muted-2)]">
          Password
          <input
            type="password"
            className="mt-1 w-full rounded border border-[var(--line)] bg-[var(--panel-2)] px-2 py-1.5 text-[12px] text-[var(--text)]"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        {error ? <div className="text-[11px] text-[var(--red)]">{error}</div> : null}
        <button
          type="submit"
          disabled={busy}
          className="rounded border border-[var(--cyan)] px-3 py-1.5 text-[12px] font-semibold text-[var(--cyan)] disabled:opacity-40"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <div className="text-[10px] text-[var(--muted-2)]">
          Roles: viewer / test_eng / process_eng / ai_eng / maint_eng / admin
        </div>
      </form>
    </div>
  );
}
