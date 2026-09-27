"""PIXEL — Phase 16 Visual Memory & Right-to-Forget Unit Tests.

Validates provenance tracking, TTL temporal expiration, search querying,
and right-to-forget deletion.
"""

from packages.contracts.multimodal import FrameSource, VisualMemoryCategory
from services.multimodal.visual_memory_manager import VisualMemoryManager


def test_visual_memory_storage_and_query() -> None:
    mgr = VisualMemoryManager(user_id="alice")
    rec = mgr.store_record(
        key="db_diagram",
        value_summary="PostgreSQL architecture schema diagram",
        category=VisualMemoryCategory.USER_APPROVED_MEMORY,
        source=FrameSource.EXTERNAL_IMAGE,
        confidence=0.99,
        user_confirmed=True,
    )

    assert rec.key == "db_diagram"
    assert rec.user_confirmed is True

    # Search
    results = mgr.query_visual_memory("PostgreSQL")
    assert len(results) == 1
    assert results[0].record_id == rec.record_id


def test_visual_memory_ttl_expiration() -> None:
    mgr = VisualMemoryManager(user_id="alice")
    mgr.store_record(
        key="temp_error",
        value_summary="Compiler error log from VSCode",
        category=VisualMemoryCategory.CURRENT_CONTEXT,
        ttl_seconds=0,  # Expired
    )

    active = mgr.get_active_records()
    assert len(active) == 0

    purged = mgr.purge_expired()
    assert purged == 1


def test_visual_memory_right_to_forget() -> None:
    mgr = VisualMemoryManager(user_id="alice")
    mgr.store_record(key="invoice_101", value_summary="Invoice screenshot for AWS bill")
    mgr.store_record(key="design_wireframe", value_summary="Mobile app design wireframe")

    # Purge single record by query
    deleted = mgr.delete_by_query_or_key("invoice")
    assert deleted == 1
    assert len(mgr.query_visual_memory("invoice")) == 0
    assert len(mgr.query_visual_memory("wireframe")) == 1

    # Purge all
    all_deleted = mgr.delete_all_visual_memories()
    assert all_deleted == 1
    assert len(mgr.get_active_records()) == 0
