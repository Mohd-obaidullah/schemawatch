from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)

SSE_KEEP_ALIVE_SECONDS = 15.0
MAX_SUBSCRIBER_QUEUE_SIZE = 100


class SSEManager:
    """Thread-safe Server-Sent Events broker.

    Distributes live drift events from background worker threads to multiple
    async HTTP SSE subscriber connections. Bounded queues guarantee that slow
    or paused consumers never block the publisher or leak memory.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    @property
    def subscriber_count(self) -> int:
        """Current number of active SSE listeners."""
        return len(self._subscribers)

    def broadcast_threadsafe(
        self,
        loop: asyncio.AbstractEventLoop,
        event_name: str,
        data: dict[str, Any],
    ) -> None:
        """Safely broadcast an event payload from a background thread to all SSE subscribers."""
        payload = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"

        def _enqueue() -> None:
            for q in list(self._subscribers):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    # Drop sample for slow subscriber without blocking
                    logger.debug("schemawatch SSE: dropped event for slow subscriber")

        if loop.is_running():
            loop.call_soon_threadsafe(_enqueue)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribe to the SSE stream with automatic keep-alive pings."""
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=MAX_SUBSCRIBER_QUEUE_SIZE)
        self._subscribers.add(queue)

        try:
            # Send initial comment so HTTP headers flush immediately
            yield ": connected\n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=SSE_KEEP_ALIVE_SECONDS)
                    yield msg
                except TimeoutError:
                    # Keep-alive ping every 15 seconds to prevent proxy/browser timeout
                    yield ": keep-alive\n\n"
        finally:
            self._subscribers.discard(queue)
