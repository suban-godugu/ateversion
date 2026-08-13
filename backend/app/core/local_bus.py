from __future__ import annotations

import asyncio
from collections import defaultdict


class LocalPubSub:
    """In-process pub/sub for single-container hosts (Hugging Face Spaces)."""

    def __init__(self) -> None:
        self._channels: dict[str, list[asyncio.Queue[str]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, message: str) -> int:
        async with self._lock:
            queues = list(self._channels.get(channel, []))
        for q in queues:
            await q.put(message)
        return len(queues)

    async def subscribe(self, channel: str) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._channels[channel].append(q)
        return q

    async def unsubscribe(self, channel: str, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            subs = self._channels.get(channel, [])
            if queue in subs:
                subs.remove(queue)


local_bus = LocalPubSub()
