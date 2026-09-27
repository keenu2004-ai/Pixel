"""Unit tests for CrossDeviceSyncManager (Mesh Context Sync, Conflict Resolution, Revocation)."""

import pytest

from packages.contracts.personalization import (
    EntityType,
    PersonalEntity,
    PersonalGoal,
)
from services.personalization.sync_manager import CrossDeviceSyncManager
from services.personalization.user_model_store import UserModelStore


@pytest.fixture
def sync_env() -> tuple[CrossDeviceSyncManager, UserModelStore]:
    store = UserModelStore(db_path=":memory:")
    mgr = CrossDeviceSyncManager(user_model_store=store)
    return mgr, store


@pytest.mark.asyncio
async def test_cross_device_sync_delta_generation_and_application(
    sync_env: tuple[CrossDeviceSyncManager, UserModelStore],
) -> None:
    mgr, store = sync_env

    # 1. Setup local data on Device A
    goal = PersonalGoal(
        user_id="user_sync",
        title="Multi-Device Mesh Networking",
    )
    await store.save_goal(goal)

    entity = PersonalEntity(
        user_id="user_sync",
        entity_type=EntityType.DEVICE,
        canonical_name="PixelPhone",
        aliases=["phone"],
    )
    await store.save_entity(entity)

    # 2. Generate delta from Device A (Phone)
    delta = await mgr.create_sync_delta(
        origin_device_id="device_phone_1",
        user_id="user_sync",
    )
    assert delta.origin_device_id == "device_phone_1"
    assert len(delta.active_goals) == 1
    assert len(delta.entities) == 1
    assert delta.signature != ""

    # 3. Create target store on Device B (Server)
    store_b = UserModelStore(db_path=":memory:")
    mgr_b = CrossDeviceSyncManager(user_model_store=store_b)

    # 4. Apply delta onto Device B
    success = await mgr_b.apply_sync_delta(delta, receiving_device_id="device_server_1")
    assert success is True

    # 5. Verify Device B has synced data
    model_b = await store_b.get_user_model("user_sync")
    assert len(model_b.active_goals) == 1
    assert model_b.active_goals[0].title == "Multi-Device Mesh Networking"
    assert len(model_b.entities) == 1


@pytest.mark.asyncio
async def test_revoked_device_sync_blocked(
    sync_env: tuple[CrossDeviceSyncManager, UserModelStore],
) -> None:
    mgr, store = sync_env
    mgr.revoke_device("compromised_device_99")

    # Delta generation from revoked device fails
    with pytest.raises(PermissionError):
        await mgr.create_sync_delta(
            origin_device_id="compromised_device_99",
            user_id="user_sync",
        )
