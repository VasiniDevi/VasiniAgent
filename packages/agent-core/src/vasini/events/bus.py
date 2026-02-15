"""Event Bus — publish/subscribe with retry + DLQ + idempotency.

In-memory implementation for tests. Production uses Redis Streams (DB 2).
"""

from __future__ import annotations

from typing import Callable, Awaitable

from vasini.events.envelope import CloudEvent
from vasini.events.dlq import DeadLetterQueue

EventHandler = Callable[[CloudEvent], Awaitable[None]]


class EventBus:
    """Abstract event bus interface."""
    async def publish(self, event: CloudEvent) -> None: ...
    def subscribe(self, event_type: str, handler: EventHandler) -> None: ...


class InMemoryEventBus(EventBus):
    def __init__(self, max_retries: int = 5) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._processed_ids: set[str] = set()
        self._max_retries = max_retries
        self.dlq = DeadLetterQueue()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: CloudEvent) -> None:
        if event.id in self._processed_ids:
            return
        self._processed_ids.add(event.id)

        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            retries = 0
            while retries < self._max_retries:
                try:
                    await handler(event)
                    break
                except Exception as e:
                    retries += 1
                    if retries >= self._max_retries:
                        self.dlq.add(event, error=str(e), retry_count=retries)
