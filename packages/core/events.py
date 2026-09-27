"""In-Process Typed Async Event Dispatcher for PIXEL."""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from packages.contracts.events import BaseEvent

logger = logging.getLogger("pixel.core.events")
E = TypeVar("E", bound=BaseEvent)
EventHandler = Callable[[E], Awaitable[None]]


class EventDispatcher:
    """Thread-safe, async in-process event bus for L0-L10 subsystem events."""

    def __init__(self) -> None:
        self._subscribers: dict[type[BaseEvent], list[EventHandler[Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: type[E], handler: EventHandler[E]) -> None:
        """Subscribes an async handler to a specific event class."""
        async with self._lock:
            self._subscribers[event_type].append(handler)

    async def unsubscribe(self, event_type: type[E], handler: EventHandler[E]) -> None:
        """Unsubscribes a handler from a specific event class."""
        async with self._lock:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    async def publish(self, event: BaseEvent) -> None:
        """Publishes an event to all subscribed handlers concurrently."""
        event_type = type(event)
        handlers = list(self._subscribers.get(event_type, []))

        if not handlers:
            return

        tasks = [self._safe_execute(handler, event) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_execute(self, handler: EventHandler[Any], event: BaseEvent) -> None:
        try:
            await handler(event)
        except Exception as err:
            logger.error(
                f"Error in event handler for {type(event).__name__} (Event ID: {event.event_id}): {err}",
                exc_info=True,
            )
