"""PIXEL — Distributed Memory Mesh Replicator.

Coordinates decentralized memory replication across nodes (PC, Android, Satellite, Server),
enforces vector clock updates, handles tombstone deletions, and manages local node stores.
"""

import uuid
from datetime import UTC, datetime

from packages.contracts.evolution import (
    ConflictRecord,
    MemoryReplicationEnvelope,
    MeshSyncState,
    ReplicatedMemoryItem,
)
from services.evolution.memory_mesh.conflict_resolver import MemoryConflictResolver


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class MemoryMeshReplicator:
    """Manages local node memory state and synchronizes with peer nodes."""

    def __init__(
        self,
        node_id: str,
        conflict_resolver: MemoryConflictResolver | None = None,
    ) -> None:
        self.node_id = node_id
        self.resolver = conflict_resolver or MemoryConflictResolver()
        self._local_store: dict[str, ReplicatedMemoryItem] = {}  # memory_id -> item
        self._conflicts: dict[str, ConflictRecord] = {}  # conflict_id -> record
        self._tombstones: dict[str, str] = {}  # memory_id -> deleted_at

    def put_item(
        self,
        memory_id: str,
        owner_user_id: str,
        content_payload: dict[str, object],
        sensitivity_class: str = "CONFIDENTIAL",
    ) -> ReplicatedMemoryItem:
        """Creates or updates a memory item locally on this node."""
        existing = self._local_store.get(memory_id)

        if existing:
            new_version = existing.version + 1
            new_vc = dict(existing.vector_clock)
            new_vc[self.node_id] = new_vc.get(self.node_id, 0) + 1
        else:
            new_version = 1
            new_vc = {self.node_id: 1}

        now = _utc_now_iso()
        item = ReplicatedMemoryItem(
            memory_id=memory_id,
            owner_user_id=owner_user_id,
            version=new_version,
            vector_clock=new_vc,
            origin_node_id=self.node_id,
            content_payload=content_payload,
            sensitivity_class=sensitivity_class,
            is_tombstone=False,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self._local_store[memory_id] = item
        return item

    def delete_item(self, memory_id: str, owner_user_id: str) -> ReplicatedMemoryItem | None:
        """Creates a tombstone deletion item for a memory record."""
        existing = self._local_store.get(memory_id)
        if not existing:
            return None

        new_vc = dict(existing.vector_clock)
        new_vc[self.node_id] = new_vc.get(self.node_id, 0) + 1

        now = _utc_now_iso()
        tombstone = ReplicatedMemoryItem(
            memory_id=memory_id,
            owner_user_id=owner_user_id,
            version=existing.version + 1,
            vector_clock=new_vc,
            origin_node_id=self.node_id,
            content_payload={},
            sensitivity_class=existing.sensitivity_class,
            is_tombstone=True,
            created_at=existing.created_at,
            updated_at=now,
        )
        self._local_store[memory_id] = tombstone
        self._tombstones[memory_id] = now
        return tombstone

    def get_item(self, memory_id: str) -> ReplicatedMemoryItem | None:
        """Retrieves a non-tombstone memory item."""
        item = self._local_store.get(memory_id)
        if not item or item.is_tombstone:
            return None
        return item

    def create_replication_envelope(self, target_node_id: str) -> MemoryReplicationEnvelope:
        """Exports all local items as a replication envelope for a target node."""
        return MemoryReplicationEnvelope(
            envelope_id=f"env-{uuid.uuid4().hex[:8]}",
            origin_node_id=self.node_id,
            target_node_id=target_node_id,
            items=list(self._local_store.values()),
            timestamp_utc=_utc_now_iso(),
            signature="mock_sig",
        )

    def receive_replication_envelope(
        self,
        envelope: MemoryReplicationEnvelope,
    ) -> tuple[int, int, list[ConflictRecord]]:
        """Processes incoming replication envelope from a peer node.

        Returns (items_converged, items_unchanged, conflicts_detected).
        """
        converged_count = 0
        unchanged_count = 0
        conflicts: list[ConflictRecord] = []

        for remote_item in envelope.items:
            local_item = self._local_store.get(remote_item.memory_id)

            if not local_item:
                # New item received
                self._local_store[remote_item.memory_id] = remote_item
                converged_count += 1
                if remote_item.is_tombstone:
                    self._tombstones[remote_item.memory_id] = remote_item.updated_at
                continue

            state, resolved_item, conflict_record = self.resolver.resolve(local_item, remote_item)

            if state == MeshSyncState.CONVERGED and resolved_item:
                self._local_store[remote_item.memory_id] = resolved_item
                converged_count += 1
                if resolved_item.is_tombstone:
                    self._tombstones[remote_item.memory_id] = resolved_item.updated_at
            elif state == MeshSyncState.NO_CONFLICT:
                unchanged_count += 1
            elif state in (MeshSyncState.CONFLICT, MeshSyncState.QUARANTINED) and conflict_record:
                self._conflicts[conflict_record.conflict_id] = conflict_record
                conflicts.append(conflict_record)

        return converged_count, unchanged_count, conflicts

    def list_active_items(self) -> list[ReplicatedMemoryItem]:
        """Lists all active non-tombstone memory items."""
        return [item for item in self._local_store.values() if not item.is_tombstone]

    def list_conflicts(self) -> list[ConflictRecord]:
        """Lists active unresolved conflicts."""
        return list(self._conflicts.values())
