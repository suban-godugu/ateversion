"""Unauthorized API + WebSocket access checks for production hardening."""

from __future__ import annotations

import asyncio
import json
import sys

import httpx
import websockets

API = "http://127.0.0.1:8000/api"
WS = "ws://127.0.0.1:8000/ws/test-floor"


def ok(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    line = f"[{status}] {name}" + (f" - {detail}" if detail else "")
    print(line.encode("ascii", errors="replace").decode("ascii"))
    if not cond:
        raise SystemExit(1)


async def main() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Health / ready (no auth)
        r = await client.get(f"{API}/health")
        ok("GET /health unauthenticated", r.status_code == 200, str(r.status_code))

        r = await client.get(f"{API}/ready")
        ok("GET /ready unauthenticated", r.status_code == 200, str(r.json().get("status")))

        # Protected API without token
        r = await client.get(f"{API}/dashboard/summary")
        ok("GET /dashboard/summary without token -> 401", r.status_code == 401, str(r.status_code))

        r = await client.get(f"{API}/kpis")
        ok("GET /kpis without token -> 401", r.status_code == 401, str(r.status_code))

        r = await client.get(f"{API}/events")
        ok("GET /events without token -> 401", r.status_code == 401, str(r.status_code))

        r = await client.get(f"{API}/maintenance")
        ok("GET /maintenance without token -> 401", r.status_code == 401, str(r.status_code))

        r = await client.get(f"{API}/test-limits")
        ok("GET /test-limits without token -> 401", r.status_code == 401, str(r.status_code))

        # Login as VIEWER
        login = await client.post(
            f"{API}/auth/login",
            json={"username": "viewer", "password": "viewer123"},
        )
        ok("viewer login", login.status_code == 200, str(login.status_code))
        viewer_token = login.json()["access_token"]
        vh = {"Authorization": f"Bearer {viewer_token}"}

        r = await client.get(f"{API}/dashboard/summary", headers=vh)
        ok("VIEWER can read dashboard", r.status_code == 200, str(r.status_code))

        # VIEWER forbidden mutations
        r = await client.post(f"{API}/maintenance/predict", headers=vh, json={})
        ok(
            "VIEWER cannot predict maintenance -> 403",
            r.status_code == 403,
            str(r.status_code),
        )

        # Find a limit id if any for approve attempt
        limits = await client.get(f"{API}/test-limits", headers=vh)
        ok("VIEWER can read test-limits", limits.status_code == 200, str(limits.status_code))
        items = limits.json().get("items") or limits.json().get("limits") or []
        if items:
            lid = items[0].get("limit_id") or items[0].get("id")
            if lid:
                r = await client.post(
                    f"{API}/test-limits/{lid}/approve",
                    headers=vh,
                    json={"comment": "unauthorized"},
                )
                ok(
                    "VIEWER cannot approve limits -> 403",
                    r.status_code == 403,
                    str(r.status_code),
                )

        # ADMIN can login
        admin = await client.post(
            f"{API}/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        ok("admin login", admin.status_code == 200, str(admin.status_code))

        # Bad password
        bad = await client.post(
            f"{API}/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        ok("bad password -> 401", bad.status_code == 401, str(bad.status_code))

    # WebSocket without token -> close 4401 (or HTTP reject)
    try:
        async with websockets.connect(WS, open_timeout=5, close_timeout=5) as ws:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                ok("WS without token rejected", False, f"received {str(msg)[:80]}")
            except websockets.exceptions.ConnectionClosed as closed:
                ok("WS without token close 4401", closed.code == 4401, f"code={closed.code}")
    except Exception as exc:
        detail = str(exc)
        code = getattr(exc, "code", None) or getattr(getattr(exc, "rcvd", None), "code", None)
        ok(
            "WS without token rejected",
            code == 4401 or "4401" in detail or "403" in detail or "401" in detail,
            detail if code is None else f"code={code}",
        )

    # VIEWER token allowed on WS
    async with httpx.AsyncClient(timeout=10.0) as client:
        login = await client.post(
            f"{API}/auth/login",
            json={"username": "viewer", "password": "viewer123"},
        )
        token = login.json()["access_token"]

    try:
        async with websockets.connect(
            f"{WS}?token={token}", open_timeout=5, close_timeout=5
        ) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            ok(
                "VIEWER WS connects and receives snapshot/heartbeat",
                data.get("kind") in {"projection_snapshot", "heartbeat", "telemetry_event"},
                data.get("kind"),
            )
    except Exception as exc:
        ok("VIEWER WS connects", False, str(exc))

    print("\nAll authorization hardening checks passed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[FAIL] harness error: {exc}", file=sys.stderr)
        raise
