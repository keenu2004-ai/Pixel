"""Typed event bus with predicate filtering and deduplication for autonomous workflows."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from packages.contracts.autonomous import AutonomousEvent, EventFilter
from packages.core.interfaces.autonomous import BaseEventBus

logger = logging.getLogger(__name__)


class EventBus(BaseEventBus):
    """In-memory event bus with pattern filtering, async dispatch, and idempotency deduplication."""

    def __init__(
        self, deduplication_window_seconds: float = 3600.0, max_history_size: int = 10000
    ) -> None:
        self._subscribers: dict[
            str, tuple[EventFilter, Callable[[AutonomousEvent], Awaitable[None]]]
        ] = {}
        self._processed_events: dict[str, datetime] = {}
        self._deduplication_window_seconds = deduplication_window_seconds
        self._max_history_size = max_history_size
        self._lock = asyncio.Lock()

    def is_duplicate(self, event: AutonomousEvent) -> bool:
        """Check if an event was previously processed within the deduplication window."""
        key = event.idempotency_key or event.event_id
        now = datetime.now(UTC)

        # Cleanup old entries if cache is too large
        if len(self._processed_events) > self._max_history_size:
            self._purge_stale_events(now)

        if key in self._processed_events:
            seen_at = self._processed_events[key]
            if (now - seen_at).total_seconds() <= self._deduplication_window_seconds:
                return True

        return False

    def mark_processed(self, event: AutonomousEvent) -> None:
        """Record an event key as processed."""
        key = event.idempotency_key or event.event_id
        self._processed_events[key] = datetime.now(UTC)

    def subscribe(
        self,
        subscriber_id: str,
        filter_pred: EventFilter,
        callback: Callable[[AutonomousEvent], Awaitable[None]],
    ) -> None:
        """Register a subscriber with predicate filter and callback."""
        self._subscribers[subscriber_id] = (filter_pred, callback)
        logger.info(
            "EventBus subscriber '%s' registered for pattern '%s'",
            subscriber_id,
            filter_pred.event_type_pattern,
        )

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Remove a subscriber by ID."""
        if subscriber_id in self._subscribers:
            del self._subscribers[subscriber_id]
            logger.info("EventBus subscriber '%s' unregistered", subscriber_id)
            return True
        return False

    async def publish(self, event: AutonomousEvent) -> int:
        """Publish an event to all matching subscribers, respecting deduplication."""
        async with self._lock:
            if self.is_duplicate(event):
                logger.warning(
                    "EventBus dropped duplicate event '%s' (idempotency_key: %s)",
                    event.event_id,
                    event.idempotency_key,
                )
                return 0

            self.mark_processed(event)

        dispatched_count = 0
        tasks = []

        for sub_id, (filt, callback) in list(self._subscribers.items()):
            if filt.matches(event):
                tasks.append(self._invoke_callback(sub_id, callback, event))
                dispatched_count += 1

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return dispatched_count

    async def _invoke_callback(
        self,
        subscriber_id: str,
        callback: Callable[[AutonomousEvent], Awaitable[None]],
        event: AutonomousEvent,
    ) -> None:
        """Safely execute subscriber callback and catch exceptions."""
        try:
            await callback(event)
        except Exception:
            logger.exception(
                "Exception in EventBus subscriber '%s' handling event '%s'",
                subscriber_id,
                event.event_id,
            )

    def _purge_stale_events(self, now: datetime) -> None:
        """Prune entries older than deduplication window."""
        stale_keys = [
            k
            for k, ts in self._processed_events.items()
            if (now - ts).total_seconds() > self._deduplication_window_seconds
        ]
        for k in stale_keys:
            del self._processed_events[k]

    def clear(self) -> None:
        """Clear all subscribers and deduplication history."""
        self._subscribers.clear()
        self._processed_events.clear()
