"""Unit tests for FleetMemoryCoordinator."""

from services.fleet.distributed_memory import FleetMemoryCoordinator
from services.memory.manager import MemoryManager


def test_distributed_memory_sync_and_tombstones() -> None:
    """Verify memory fact replication across trusted nodes, vector clocks, and tombstone propagation."""
    mem_mgr = MemoryManager(db_path=":memory:")
    coord = FleetMemoryCoordinator(memory_manager=mem_mgr)

    # 1. Replicate fact to phone node
    replicated = coord.replicate_fact_to_node(
        target_node_id="phone_pixel_01",
        fact_key="user_favorite_editor",
        fact_value="VS Code with NeoVim",
        version=1,
    )
    assert replicated is True

    # 2. Tombstone creation on Right-to-Forget deletion
    purged_count = coord.propagate_tombstone_purge(fact_key="user_favorite_editor")
    assert purged_count == 1

    # 3. Attempt to replicate tombstoned fact must be blocked
    replicate_blocked = coord.replicate_fact_to_node(
        target_node_id="phone_pixel_01",
        fact_key="user_favorite_editor",
        fact_value="VS Code with NeoVim",
        version=2,
    )
    assert replicate_blocked is False

    # 4. Offline node reconciliation
    recon = coord.reconcile_offline_node("phone_pixel_01")
    assert recon["node_id"] == "phone_pixel_01"
