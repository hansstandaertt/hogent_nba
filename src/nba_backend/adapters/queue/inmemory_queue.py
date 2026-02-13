from __future__ import annotations

import asyncio


class InMemoryCalculationEventQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict] = asyncio.Queue()

    async def publish(self, payload: dict) -> None:
        await self._queue.put(payload)

    async def consume(self) -> dict:
        return await self._queue.get()
