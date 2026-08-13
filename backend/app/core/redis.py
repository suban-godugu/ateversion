from __future__ import annotations

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.local_bus import local_bus

_redis: redis.Redis | None = None
_memory_mode: bool | None = None


def _is_memory() -> bool:
    global _memory_mode
    if _memory_mode is None:
        _memory_mode = get_settings().use_memory_bus
    return _memory_mode


async def get_redis() -> redis.Redis | None:
    """Returns Redis client, or None when using in-process bus."""
    if _is_memory():
        return None
    global _redis
    if _redis is None:
        _redis = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def publish_event(channel: str, message: str) -> None:
    if _is_memory():
        await local_bus.publish(channel, message)
        return
    client = await get_redis()
    assert client is not None
    await client.publish(channel, message)


async def ping_redis() -> bool:
    if _is_memory():
        return True
    try:
        client = await get_redis()
        assert client is not None
        return (await client.ping()) is True
    except Exception:
        return False
