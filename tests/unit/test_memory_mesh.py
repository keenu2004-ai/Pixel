"""Unit tests for Distributed Memory Mesh Replicator and Conflict Resolver."""

from packages.contracts.evolution import MeshSyncState
from services.evolution.memory_mesh.replicator import MemoryMeshReplicator


def test_memory_mesh_basic_sync() -> None:
    node_pc = MemoryMeshReplicator(node_id="node-pc")
    node_android = MemoryMeshReplicator(node_id="node-android")

    # Put item on PC
    item1 = node_pc.put_item(
        memory_id="fact-001",
        owner_user_id="user-vaibhav",
        content_payload={"topic": "ui_theme", "value": "dark"},
    )
    assert item1.version == 1
    assert item1.vector_clock == {"node-pc": 1}

    # Replicate from PC to Android
    envelope = node_pc.create_replication_envelope(target_node_id="node-android")
    converged, unchanged, conflicts = node_android.receive_replication_envelope(envelope)

    assert converged == 1
    assert unchanged == 0
    assert len(conflicts) == 0

    # Verify Android has the item
    synced_item = node_android.get_item("fact-001")
    assert synced_item is not None
    assert synced_item.content_payload == {"topic": "ui_theme", "value": "dark"}


def test_memory_mesh_tombstone_propagation() -> None:
    node_pc = MemoryMeshReplicator(node_id="node-pc")
    node_android = MemoryMeshReplicator(node_id="node-android")

    # Put item on PC and sync to Android
    node_pc.put_item("fact-002", "user-vaibhav", {"fact": "Secret notes"})
    env1 = node_pc.create_replication_envelope("node-android")
    node_android.receive_replication_envelope(env1)

    assert node_android.get_item("fact-002") is not None

    # Delete on PC (create tombstone)
    tombstone = node_pc.delete_item("fact-002", "user-vaibhav")
    assert tombstone is not None
    assert tombstone.is_tombstone is True
    assert node_pc.get_item("fact-002") is None

    # Sync tombstone to Android
    env2 = node_pc.create_replication_envelope("node-android")
    node_android.receive_replication_envelope(env2)

    # Verify Android deleted the item (no resurrection)
    assert node_android.get_item("fact-002") is None


def test_memory_mesh_divergent_conflict_quarantine() -> None:
    node_pc = MemoryMeshReplicator(node_id="node-pc")
    node_android = MemoryMeshReplicator(node_id="node-android")

    # Base sync
    node_pc.put_item("fact-003", "user-vaibhav", {"setting": "initial"})
    node_android.receive_replication_envelope(node_pc.create_replication_envelope("node-android"))

    # Concurrent edits on both nodes
    node_pc.put_item("fact-003", "user-vaibhav", {"setting": "pc_value"})
    node_android.put_item("fact-003", "user-vaibhav", {"setting": "android_value"})

    # Sync Android to PC -> Divergent concurrent conflict
    env_android = node_android.create_replication_envelope("node-pc")
    converged, unchanged, conflicts = node_pc.receive_replication_envelope(env_android)

    assert len(conflicts) == 1
    assert conflicts[0].resolution_state == MeshSyncState.CONFLICT
    assert len(node_pc.list_conflicts()) == 1
