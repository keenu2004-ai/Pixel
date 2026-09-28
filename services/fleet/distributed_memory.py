"""PIXEL — Phase 17 Fleet Distributed Memory & Context Synchronization Coordinator.

Coordinates bounded memory context replication, vector clock versioning,
right-to-forget tombstone propagation, and offline reconciliation.
"""

from typing import Any

from services.memory.manager import MemoryManager


class FleetMemoryCoordinator:
    """Synchronizes bounded memory state across trusted edge nodes."""

    def __init__(self, memory_manager: MemoryManager | None = None) -> None:
        self._memory_manager = memory_manager
        self._node_vector_clocks: dict[str, dict[str, int]] = {}  # node_id -> {fact_key: version}
        self._tombstones: set[str] = set()

    def replicate_fact_to_node(
        self,
        target_node_id: str,
        fact_key: str,
        fact_value: str,
        version: int = 1,
    ) -> bool:
        """Replicates a verified fact to an edge node if not tombstoned."""
        if fact_key in self._tombstones:
            return False

        if target_node_id not in self._node_vector_clocks:
            self._node_vector_clocks[target_node_id] = {}

        current_ver = self._node_vector_clocks[target_node_id].get(fact_key, 0)
        if version >= current_ver:
            self._node_vector_clocks[target_node_id][fact_key] = version
            return True
        return False

    def propagate_tombstone_purge(self, fact_key: str) -> int:
        """Propagates Right-to-Forget deletion tombstone across all node vector clocks."""
        self._tombstones.add(fact_key)
        affected_nodes_count = 0

        for _node_id, facts in self._node_vector_clocks.items():
            if fact_key in facts:
                del facts[fact_key]
                affected_nodes_count += 1

        return affected_nodes_count

    def reconcile_offline_node(self, node_id: str) -> dict[str, Any]:
        """Reconciles memory state after an edge node reconnects from offline mode."""
        node_facts = self._node_vector_clocks.get(node_id, {})
        # Purge any facts that received tombstones while offline
        purged_keys = [k for k in node_facts if k in self._tombstones]
        for k in purged_keys:
            del node_facts[k]

        return {
            "node_id": node_id,
            "active_facts_count": len(node_facts),
            "purged_tombstones_count": len(purged_keys),
        }
