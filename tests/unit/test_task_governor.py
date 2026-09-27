"""Unit tests for TaskGovernor and concurrency regulation."""

import pytest

from services.autonomous.governor import TaskGovernor


@pytest.mark.asyncio
async def test_task_governor_slot_capacity() -> None:
    gov = TaskGovernor(max_concurrent_tasks=2)

    # Acquire 2 slots
    assert await gov.acquire_task_slot("task_1")
    assert await gov.acquire_task_slot("task_2")
    assert gov.get_active_task_count() == 2

    # Third slot must be denied
    assert not await gov.acquire_task_slot("task_3")

    # Release a slot
    await gov.release_task_slot("task_1")
    assert gov.get_active_task_count() == 1

    # Now task_3 can acquire
    assert await gov.acquire_task_slot("task_3")
    assert gov.get_active_task_count() == 2
