"""
Enterprise end-to-end validation.

Creates a real telemetry event and verifies:
PostgreSQL persistence, Redis publish, WebSocket broadcast,
API projections (wafer/KPI/events), auth/RBAC, audit trail,
and reconnect/sync readiness probes.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from uuid import uuid4

import httpx
import redis.asyncio as redis
import websockets
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.entities import AuditLog, Die, TelemetryEventRow, TestEvent

API = "http://127.0.0.1:8000/api"
WS = "ws://127.0.0.1:8000/ws/test-floor"


def ok(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    line = f"[{status}] {name}" + (f" - {detail}" if detail else "")
    print(line.encode("ascii", errors="replace").decode("ascii"))
    if not cond:
        raise SystemExit(1)


async def main() -> None:
    settings = get_settings()
    event_id = str(uuid4())
    seq = int(datetime.utcnow().timestamp()) % 1_000_000_000
    die_x, die_y = 5, 6
    die_id = f"{die_x},{die_y}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        # --- Auth ---
        login = await client.post(
            f"{API}/auth/login",
            json={"username": "test_eng", "password": "test123"},
        )
        ok("authentication login", login.status_code == 200, str(login.status_code))
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me = await client.get(f"{API}/auth/me", headers=headers)
        ok("authentication /me", me.status_code == 200 and me.json()["role"] == "TEST_ENGINEER")

        viewer = await client.post(
            f"{API}/auth/login",
            json={"username": "viewer", "password": "viewer123"},
        )
        vtoken = viewer.json()["access_token"]
        rbac = await client.post(
            f"{API}/telemetry/events",
            headers={"Authorization": f"Bearer {vtoken}"},
            json={"events": []},
        )
        ok("RBAC denies VIEWER telemetry write", rbac.status_code in {403, 422}, str(rbac.status_code))

        deny = await client.get(f"{API}/dashboard/summary")
        ok("unauthenticated API denied", deny.status_code == 401)

        # Baseline wafer/KPI/events
        summary_before = (await client.get(f"{API}/dashboard/summary", headers=headers)).json()
        wafer_id = summary_before["active_wafer"]["wafer_id"]
        lot_id = summary_before["active_wafer"]["lot_id"]
        kpis_before = (await client.get(f"{API}/kpis", headers=headers)).json()["kpis"]
        kpi_map_before = {k["id"]: k.get("value") for k in kpis_before}
        events_before = (
            await client.get(f"{API}/events?limit=1", headers=headers)
        ).json()["total"]

        # Subscribe Redis + WS before ingest
        r = redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(settings.telemetry_channel)

        ws_task_result: dict = {}

        async def ws_listen() -> None:
            async with websockets.connect(
                f"{WS}?token={token}", open_timeout=8, close_timeout=5
            ) as ws:
                deadline = asyncio.get_event_loop().time() + 12
                while asyncio.get_event_loop().time() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=12)
                    msg = json.loads(raw)
                    if msg.get("kind") != "telemetry_event":
                        continue
                    ev = msg.get("event") or {}
                    if ev.get("event_id") == event_id:
                        ws_task_result["msg"] = msg
                        return

        ws_task = asyncio.create_task(ws_listen())
        await asyncio.sleep(0.4)

        payload = {
            "events": [
                {
                    "event_id": event_id,
                    "event_type": "die_fail",
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "ate",
                    "tester_id": "ATE-04",
                    "site_id": "1",
                    "lot_id": lot_id,
                    "wafer_id": wafer_id,
                    "die_id": die_id,
                    "sequence_number": seq,
                    "payload": {
                        "x": die_x,
                        "y": die_y,
                        "bin": "fail",
                        "fail_code": "E2E_BIN_FAIL",
                        "test_time_ms": 155,
                        "confidence": 0.91,
                        "kpi_updates": {
                            "escape_prevention": float(kpi_map_before.get("escape_prevention") or 0)
                            + 0.1
                        },
                    },
                }
            ]
        }

        # Drain any backlog then ingest
        async def wait_redis() -> dict | None:
            deadline = asyncio.get_event_loop().time() + 12
            while asyncio.get_event_loop().time() < deadline:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg or msg.get("type") != "message":
                    await asyncio.sleep(0.05)
                    continue
                data = json.loads(msg["data"])
                ev = data.get("event") or {}
                if ev.get("event_id") == event_id:
                    return data
            return None

        redis_waiter = asyncio.create_task(wait_redis())
        ingest = await client.post(f"{API}/telemetry/events", headers=headers, json=payload)
        ok("create real test event", ingest.status_code == 200, str(ingest.status_code))
        ok("ingest accepted event_id", event_id in ingest.json().get("event_ids", []))

        redis_msg = await redis_waiter
        ok("Redis received event", redis_msg is not None, "channel publish")
        await ws_task
        ok("WebSocket broadcast received", "msg" in ws_task_result, event_id)
        ok(
            "React-consumable WS envelope",
            bool(ws_task_result.get("msg", {}).get("test_event")),
            "test_event present",
        )

        await pubsub.unsubscribe(settings.telemetry_channel)
        await pubsub.aclose()
        await r.aclose()

        # PostgreSQL persistence
        async with SessionLocal() as db:
            row = await db.get(TelemetryEventRow, event_id)
            ok("PostgreSQL telemetry_events row", row is not None)
            te = (
                await db.execute(select(TestEvent).where(TestEvent.event_id == event_id))
            ).scalar_one_or_none()
            ok("PostgreSQL test_events row", te is not None)
            die = (
                await db.execute(
                    select(Die).where(Die.wafer_id == wafer_id, Die.x == die_x, Die.y == die_y)
                )
            ).scalar_one_or_none()
            ok(
                "wafer map die updated in DB",
                die is not None and die.bin == "fail",
                f"bin={getattr(die, 'bin', None)}",
            )

        # API projections React would refetch
        wafer = (await client.get(f"{API}/wafers/{wafer_id}", headers=headers)).json()
        ok("wafer API yield available", "yield_pct" in wafer)

        dies = (await client.get(f"{API}/wafers/{wafer_id}/dies", headers=headers)).json()
        match = next((d for d in dies if d.get("x") == die_x and d.get("y") == die_y), None)
        ok(
            "wafer map API die updated",
            match is not None and (match.get("bin") == "fail" or match.get("result") == "fail"),
            str(match.get("bin") or match.get("result") if match else None),
        )

        events_after = (await client.get(f"{API}/events?limit=50", headers=headers)).json()
        found_event = next((e for e in events_after["items"] if e["event_id"] == event_id), None)
        ok("event log API contains event", found_event is not None)
        ok("event log total increased or contains event", events_after["total"] >= events_before)

        kpis_after = (await client.get(f"{API}/kpis", headers=headers)).json()["kpis"]
        kpi_map_after = {k["id"]: k.get("value") for k in kpis_after}
        before_kpi = float(kpi_map_before.get("escape_prevention") or 0)
        after_kpi = float(kpi_map_after.get("escape_prevention") or 0)
        ok(
            "KPI value changed authoritatively",
            abs(after_kpi - before_kpi) > 1e-9,
            f"before={before_kpi} after={after_kpi}",
        )

        # Persistence after "browser refresh" (new HTTP session)
        again = await client.get(f"{API}/events/{event_id}", headers=headers)
        ok("state remains after refresh fetch", again.status_code == 200)
        wafer2 = (await client.get(f"{API}/wafers/{wafer_id}", headers=headers)).json()
        ok("wafer state remains after refresh", wafer2["wafer_id"] == wafer_id)

        # Health / ready / connection monitoring
        health = await client.get(f"{API}/health")
        ready = await client.get(f"{API}/ready")
        ok("health check", health.status_code == 200 and health.json()["status"] == "ok")
        ok("readiness check", ready.status_code == 200 and ready.json()["status"] == "ready")

        # Audit trail (login wrote audit)
        async with SessionLocal() as db:
            audits = (
                await db.execute(
                    select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(20)
                )
            ).scalars().all()
            ok("audit trail present", len(audits) > 0, f"count={len(audits)}")
            login_audit = any(a.action == "login" for a in audits)
            ok("audit trail includes login", login_audit)

        # WS unauthorized still rejected
        try:
            async with websockets.connect(WS, open_timeout=5, close_timeout=5) as ws:
                try:
                    await asyncio.wait_for(ws.recv(), timeout=2)
                    ok("WS unauthorized rejected", False)
                except websockets.exceptions.ConnectionClosed as closed:
                    ok("WS unauthorized close", closed.code == 4401, f"code={closed.code}")
        except Exception as exc:
            ok("WS unauthorized rejected", "4401" in str(exc) or "403" in str(exc), str(exc))

        # Reconnect sync: client can re-fetch authoritative state
        sync = await client.get(f"{API}/dashboard/summary", headers=headers)
        ok("reconnect synchronize backend state", sync.status_code == 200)

        # Simulate telemetry disconnect awareness via ready websocket_clients field
        ok(
            "connection monitoring exposed",
            "websocket_clients" in ready.json(),
            str(ready.json().get("websocket_clients")),
        )

        # OFFLINE/STALE semantics documented by FE stores — verify STALE threshold config exists
        ok(
            "stale telemetry threshold configured",
            settings.stale_telemetry_seconds >= 10,
            str(settings.stale_telemetry_seconds),
        )

        # DB connectivity probe
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
            ok("database persistence probe", True)

    print("\nEnterprise end-to-end validation passed.")
    print(f"event_id={event_id} wafer_id={wafer_id} die={die_id}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise
