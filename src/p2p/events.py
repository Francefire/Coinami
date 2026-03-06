"""Server-Sent Events (SSE) event bus for real-time data-flow visibility.

Provides an asyncio-based pub/sub system.  Each SSE client gets its own
``asyncio.Queue`` so it receives every event independently.

Event format (JSON):
    {
        "event": "tx:received",
        "data": { ... },       # event-specific payload
        "timestamp": 1709...   # Unix epoch (float)
    }
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any


class EventBus:
    """Broadcast events to all connected SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict]] = []

    # ------------------------------------------------------------------
    # Subscriber management
    # ------------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue[dict]:
        """Register a new subscriber and return its personal queue."""
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict]) -> None:
        """Remove a subscriber queue (called on SSE disconnect)."""
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Push an event to every subscriber queue.

        Parameters
        ----------
        event:
            Dotted event name, e.g. ``"tx:received"``.
        data:
            Arbitrary JSON-serialisable payload.
        """
        message = {
            "event": event,
            "data": data or {},
            "timestamp": time.time(),
        }
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Drop events for slow consumers rather than blocking
                pass

    # ------------------------------------------------------------------
    # SSE streaming helper
    # ------------------------------------------------------------------

    async def stream(self, queue: asyncio.Queue[dict]):
        """Async generator that yields SSE-formatted strings.

        Usage with FastAPI::

            @app.get("/events")
            async def sse():
                q = event_bus.subscribe()
                return StreamingResponse(event_bus.stream(q), ...)
        """
        try:
            while True:
                message = await queue.get()
                line = f"event: {message['event']}\ndata: {json.dumps(message)}\n\n"
                yield line
        except asyncio.CancelledError:
            pass
        finally:
            self.unsubscribe(queue)
