from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.local_bus import local_bus
from app.core.logging import get_logger
from app.core.rate_limit import ws_limiter
from app.core.rbac import Permission, has_permission
from app.core.redis import get_redis
from app.core.security import decode_access_token

router = APIRouter()
logger = get_logger("websocket")


@dataclass
class ClientState:
    websocket: WebSocket
    user: str
    role: str
    last_seen: float = field(default_factory=time.time)
    last_seq: int | None = None
    seen_event_ids: set[str] = field(default_factory=set)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[WebSocket, ClientState] = {}

    async def connect(self, websocket: WebSocket, *, user: str, role: str) -> ClientState:
        await websocket.accept()
        state = ClientState(websocket=websocket, user=user, role=role)
        self.active[websocket] = state
        logger.info("ws_connected", extra={"user": user, "role": role})
        return state

    def disconnect(self, websocket: WebSocket) -> None:
        state = self.active.pop(websocket, None)
        if state:
            logger.info("ws_disconnected", extra={"user": state.user, "role": state.role})

    async def broadcast(self, message: str) -> None:
        dead: list[WebSocket] = []
        for ws in list(self.active.keys()):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def mark_event(self, state: ClientState, event_id: str | None, sequence: int | None) -> dict:
        meta: dict = {"duplicate": False, "sequence_gap": False}
        if event_id:
            if event_id in state.seen_event_ids:
                meta["duplicate"] = True
            else:
                state.seen_event_ids.add(event_id)
                if len(state.seen_event_ids) > 2000:
                    state.seen_event_ids = set(list(state.seen_event_ids)[-1000:])
        if sequence is not None:
            if state.last_seq is not None and sequence > state.last_seq + 1:
                meta["sequence_gap"] = True
                meta["expected_seq"] = state.last_seq + 1
                meta["got_seq"] = sequence
            if state.last_seq is None or sequence >= state.last_seq:
                state.last_seq = sequence
        state.last_seen = time.time()
        return meta


manager = ConnectionManager()


def _extract_token(websocket: WebSocket, token: str | None) -> str | None:
    if token:
        return token
    auth = websocket.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return websocket.query_params.get("token")


async def _send_envelope(state: ClientState, data: str) -> None:
    try:
        envelope = json.loads(data)
        event = envelope.get("event") or {}
        meta = manager.mark_event(
            state,
            event.get("event_id"),
            event.get("sequence_number"),
        )
        envelope["stream_meta"] = meta
        await state.websocket.send_text(json.dumps(envelope, default=str))
    except Exception:
        await state.websocket.send_text(str(data))


@router.websocket("/ws/test-floor")
async def test_floor_ws(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> None:
    settings = get_settings()
    client = websocket.client.host if websocket.client else "unknown"
    try:
        ws_limiter.check(f"{client}:ws")
    except Exception:
        await websocket.close(code=1008)
        return

    raw_token = _extract_token(websocket, token)
    if not settings.auth_disabled:
        if not raw_token:
            await websocket.accept()
            await websocket.close(code=4401)
            return
        try:
            payload = decode_access_token(raw_token)
            role = str(payload.get("role", ""))
            user = str(payload.get("username") or payload.get("sub"))
            if not has_permission(role, Permission.STREAM_WS):
                await websocket.accept()
                await websocket.close(code=4403)
                return
        except ValueError:
            await websocket.accept()
            await websocket.close(code=4401)
            return
    else:
        user, role = "dev", "ADMIN"

    state = await manager.connect(websocket, user=user, role=role)
    local_queue = None
    pubsub = None

    async def relay_redis() -> None:
        assert pubsub is not None
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if data is None:
                continue
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            await _send_envelope(state, str(data))

    async def relay_memory() -> None:
        assert local_queue is not None
        while True:
            data = await local_queue.get()
            await _send_envelope(state, data)

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(15)
            try:
                await state.websocket.send_text(
                    json.dumps(
                        {
                            "kind": "heartbeat",
                            "server_time": time.time(),
                            "status": "LIVE",
                        }
                    )
                )
            except Exception:
                break

    if settings.use_memory_bus:
        local_queue = await local_bus.subscribe(settings.telemetry_channel)
        relay_task = asyncio.create_task(relay_memory())
    else:
        redis = await get_redis()
        assert redis is not None
        pubsub = redis.pubsub()
        await pubsub.subscribe(settings.telemetry_channel)
        relay_task = asyncio.create_task(relay_redis())

    hb_task = asyncio.create_task(heartbeat())
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "kind": "projection_snapshot",
                    "event": None,
                    "summary": None,
                    "status": "connected",
                    "user": user,
                    "role": role,
                    "bus": "memory" if settings.use_memory_bus else "redis",
                }
            )
        )
        while True:
            msg = await websocket.receive_text()
            state.last_seen = time.time()
            if msg in {"ping", '{"kind":"ping"}'}:
                await websocket.send_text(json.dumps({"kind": "pong", "server_time": time.time()}))
            else:
                try:
                    body = json.loads(msg)
                    if body.get("kind") == "ping":
                        await websocket.send_text(
                            json.dumps({"kind": "pong", "server_time": time.time()})
                        )
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        relay_task.cancel()
        hb_task.cancel()
        if local_queue is not None:
            await local_bus.unsubscribe(settings.telemetry_channel, local_queue)
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(settings.telemetry_channel)
                await pubsub.aclose()
            except Exception:
                pass
        manager.disconnect(websocket)
