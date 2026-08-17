from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable

from app.agent.contracts import SarahEvent

EventHandler = Callable[[SarahEvent], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._handlers[topic].append(handler)

    async def publish(self, event: SarahEvent) -> None:
        handlers = [*self._handlers.get(event.topic, []), *self._handlers.get("*", [])]
        if handlers:
            await asyncio.gather(*(handler(event) for handler in handlers), return_exceptions=True)
