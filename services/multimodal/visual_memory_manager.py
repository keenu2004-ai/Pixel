"""PIXEL — Phase 16 Visual Memory & Provenance Manager.

Maintains structured visual facts, enforce TTL-based automatic expiration,
tracks derivation provenance, and executes right-to-forget deletion.
"""

from packages.contracts.multimodal import (
    FrameSource,
    VisualMemoryCategory,
    VisualMemoryRecord,
)


class VisualMemoryManager:
    """Manages visual knowledge, temporal expiration, and right-to-forget purges."""

    def __init__(self, user_id: str = "default_user") -> None:
        self._user_id = user_id
        self._records: dict[str, VisualMemoryRecord] = {}

    def store_record(
        self,
        key: str,
        value_summary: str,
        category: VisualMemoryCategory = VisualMemoryCategory.TEMPORARY_CONTEXT,
        source: FrameSource = FrameSource.DESKTOP_SCREEN,
        confidence: float = 1.0,
        user_confirmed: bool = False,
        ttl_seconds: int | None = 3600,
    ) -> VisualMemoryRecord:
        """Stores a visual memory record with provenance metadata."""
        record = VisualMemoryRecord(
            user_id=self._user_id,
            category=category,
            key=key,
            value_summary=value_summary,
            source_frame_source=source,
            confidence=confidence,
            user_confirmed=user_confirmed,
            is_active=True,
            ttl_seconds=ttl_seconds,
        )
        self._records[record.record_id] = record
        return record

    def get_active_records(self) -> list[VisualMemoryRecord]:
        """Returns all non-expired, active visual memory records."""
        active: list[VisualMemoryRecord] = []
        for record in self._records.values():
            if not record.is_expired():
                active.append(record)
        return active

    def query_visual_memory(self, query: str) -> list[VisualMemoryRecord]:
        """Searches active visual memories matching a query."""
        q = query.lower()
        results: list[VisualMemoryRecord] = []
        for record in self.get_active_records():
            if q in record.key.lower() or q in record.value_summary.lower():
                results.append(record)
        return results

    def purge_expired(self) -> int:
        """Removes all expired visual contexts."""
        expired_ids = [r_id for r_id, record in self._records.items() if record.is_expired()]
        for r_id in expired_ids:
            del self._records[r_id]
        return len(expired_ids)

    def delete_by_query_or_key(self, query_or_key: str) -> int:
        """Executes right-to-forget visual memory deletion."""
        target = query_or_key.lower().strip()
        to_delete = []
        for r_id, record in self._records.items():
            if target in record.key.lower() or target in record.value_summary.lower():
                to_delete.append(r_id)

        for r_id in to_delete:
            del self._records[r_id]

        return len(to_delete)

    def delete_all_visual_memories(self) -> int:
        """Purges all visual memories for the user."""
        count = len(self._records)
        self._records.clear()
        return count
