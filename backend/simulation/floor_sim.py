"""
Development floor simulator.

Publishes events through the production ingest API only.
Does not bypass PostgreSQL / Redis / WebSocket.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime
from uuid import uuid4

import httpx

API = os.environ.get("WYI_API", "http://127.0.0.1:8000/api")
USER = os.environ.get("WYI_SIM_USER", "test_eng")
PASSWORD = os.environ.get("WYI_SIM_PASSWORD", "test123")


async def login(client: httpx.AsyncClient) -> str:
    r = await client.post(f"{API}/auth/login", json={"username": USER, "password": PASSWORD})
    r.raise_for_status()
    return r.json()["access_token"]


async def emit_once(client: httpx.AsyncClient, token: str, seq: int) -> str:
    event_id = str(uuid4())
    body = {
        "events": [
            {
                "event_id": event_id,
                "event_type": "die_pass",
                "timestamp": datetime.utcnow().isoformat(),
                "source": "ate",
                "tester_id": "ATE-04",
                "site_id": "1",
                "lot_id": "24601-07",
                "wafer_id": "W-24601-07",
                "die_id": "3,4",
                "sequence_number": seq,
                "payload": {
                    "x": 3,
                    "y": 4,
                    "bin": "pass",
                    "test_time_ms": 120,
                    "confidence": 0.97,
                },
            }
        ]
    }
    r = await client.post(
        f"{API}/telemetry/events",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    r.raise_for_status()
    return event_id


async def run(interval: float, count: int | None) -> None:
    seq = 8_000_000
    n = 0
    async with httpx.AsyncClient(timeout=20.0) as client:
        token = await login(client)
        while count is None or n < count:
            eid = await emit_once(client, token, seq)
            print(f"[simulation] ingested {eid} seq={seq}")
            seq += 1
            n += 1
            if count is not None and n >= count:
                break
            await asyncio.sleep(interval)


def main() -> None:
    p = argparse.ArgumentParser(description="Dev-only wafer floor simulator")
    p.add_argument("--interval", type=float, default=5.0)
    p.add_argument("--count", type=int, default=None, help="Finite emissions; omit for continuous")
    args = p.parse_args()
    asyncio.run(run(args.interval, args.count))


if __name__ == "__main__":
    main()
