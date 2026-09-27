"""PIXEL — Distributed Memory Mesh Conflict Resolver.

Determines causality using vector clocks, detects concurrent edits, resolves deterministic convergence,
and isolates unresolvable conflicts into quarantine.
"""

import uuid

from packages.contracts.evolution import (
    ConflictRecord,
    MeshSyncState,
    ReplicatedMemoryItem,
)


def _compare_vector_clocks(vc1: dict[str, int], vc2: dict[str, int]) -> str:
    """Compares two vector clocks.

    Returns:
    - 'EQUAL' if identical
    - 'GREATER' if vc1 >= vc2 for all nodes and > for at least one
    - 'LESS' if vc1 <= vc2 for all nodes and < for at least one
    - 'CONCURRENT' if divergent (vc1 > vc2 on some nodes, vc2 > vc1 on others)
    """
    all_keys = set(vc1.keys()).union(set(vc2.keys()))
    greater = False
    less = False

    for k in all_keys:
        v1 = vc1.get(k, 0)
        v2 = vc2.get(k, 0)
        if v1 > v2:
            greater = True
        elif v1 < v2:
            less = True

    if greater and not less:
        return "GREATER"
    elif less and not greater:
        return "LESS"
    elif not greater and not less:
        return "EQUAL"
    else:
        return "CONCURRENT"


class MemoryConflictResolver:
    """Resolves replication conflicts between distributed memory nodes."""

    def resolve(
        self,
        local_item: ReplicatedMemoryItem,
        remote_item: ReplicatedMemoryItem,
    ) -> tuple[MeshSyncState, ReplicatedMemoryItem | None, ConflictRecord | None]:
        """Compares local and remote memory items and resolves the converged state."""
        # 1. Check user ownership boundary
        if local_item.owner_user_id != remote_item.owner_user_id:
            conflict = ConflictRecord(
                conflict_id=f"conf-user-{uuid.uuid4().hex[:8]}",
                memory_id=local_item.memory_id,
                local_version=local_item.version,
                remote_version=remote_item.version,
                local_item=local_item.model_dump(),
                remote_item=remote_item.model_dump(),
                resolution_state=MeshSyncState.QUARANTINED,
            )
            return MeshSyncState.QUARANTINED, None, conflict

        # 2. Vector clock comparison
        comp = _compare_vector_clocks(local_item.vector_clock, remote_item.vector_clock)

        if comp == "EQUAL":
            return MeshSyncState.NO_CONFLICT, local_item, None
        elif comp == "GREATER":
            # Local is strictly newer
            return MeshSyncState.NO_CONFLICT, local_item, None
        elif comp == "LESS":
            # Remote is strictly newer
            return MeshSyncState.CONVERGED, remote_item, None

        # 3. Concurrent vector clocks
        # Handle Tombstone priority: Tombstones with equal or higher version take precedence
        if remote_item.is_tombstone and not local_item.is_tombstone:
            # Merged vector clock
            merged_vc = {
                k: max(local_item.vector_clock.get(k, 0), remote_item.vector_clock.get(k, 0))
                for k in set(local_item.vector_clock.keys()).union(
                    set(remote_item.vector_clock.keys())
                )
            }
            converged = remote_item.model_copy(
                update={
                    "vector_clock": merged_vc,
                    "version": max(local_item.version, remote_item.version) + 1,
                }
            )
            return MeshSyncState.CONVERGED, converged, None

        # Check identical content payload
        if local_item.content_payload == remote_item.content_payload:
            merged_vc = {
                k: max(local_item.vector_clock.get(k, 0), remote_item.vector_clock.get(k, 0))
                for k in set(local_item.vector_clock.keys()).union(
                    set(remote_item.vector_clock.keys())
                )
            }
            converged = local_item.model_copy(
                update={
                    "vector_clock": merged_vc,
                    "version": max(local_item.version, remote_item.version) + 1,
                }
            )
            return MeshSyncState.CONVERGED, converged, None

        # Genuine concurrent divergence -> Flag CONFLICT and quarantine
        conflict = ConflictRecord(
            conflict_id=f"conf-{uuid.uuid4().hex[:8]}",
            memory_id=local_item.memory_id,
            local_version=local_item.version,
            remote_version=remote_item.version,
            local_item=local_item.model_dump(),
            remote_item=remote_item.model_dump(),
            resolution_state=MeshSyncState.CONFLICT,
        )
        return MeshSyncState.CONFLICT, None, conflict
