"""Unit tests for AssistantLifecycleHardener."""

from packages.contracts.agent import AgentExecutionStatus, AgentState
from services.voice_gateway.lifecycle_hardener import (
    AssistantLifecycleHardener,
    LifecycleEvent,
)


def test_lifecycle_background_and_foreground() -> None:
    hardener = AssistantLifecycleHardener()

    # Enter Background
    res_bg = hardener.handle_lifecycle_event(LifecycleEvent.APP_BACKGROUND)
    assert res_bg["status"] == "ADAPTED_BACKGROUND"
    assert hardener.is_in_background

    # Return to Foreground
    res_fg = hardener.handle_lifecycle_event(LifecycleEvent.APP_FOREGROUND)
    assert res_fg["status"] == "RESUMED_FOREGROUND"
    assert not hardener.is_in_background


def test_lifecycle_doze_adaptation() -> None:
    hardener = AssistantLifecycleHardener()

    # Enter Doze
    res_doze = hardener.handle_lifecycle_event(LifecycleEvent.DOZE_MODE_ENTER)
    assert res_doze["status"] == "DOZE_SUSPENDED"
    assert hardener.is_doze_active

    # Exit Doze
    res_exit = hardener.handle_lifecycle_event(LifecycleEvent.DOZE_MODE_EXIT)
    assert res_exit["status"] == "DOZE_RESTORED"
    assert not hardener.is_doze_active


def test_permission_revocation_and_restoration() -> None:
    hardener = AssistantLifecycleHardener()
    assert hardener.verify_action_permission("CALL_PHONE")

    # Revoke permission
    hardener.handle_lifecycle_event(LifecycleEvent.PERMISSION_REVOKED, {"permission": "CALL_PHONE"})
    assert not hardener.verify_action_permission("CALL_PHONE")

    # Restore permission
    hardener.handle_lifecycle_event(
        LifecycleEvent.PERMISSION_RESTORED, {"permission": "CALL_PHONE"}
    )
    assert hardener.verify_action_permission("CALL_PHONE")


def test_checkpoint_hydration_on_boot_or_crash() -> None:
    hardener = AssistantLifecycleHardener()
    state = AgentState(
        task_id="task_crash_01",
        user_query="Run tests and fix failures",
        status=AgentExecutionStatus.EXECUTING,
    )

    # Save checkpoint before process termination
    cp = hardener.save_checkpoint(state)
    assert cp.task_id == "task_crash_01"

    # Simulate boot/restart recovery
    recovered = hardener.recover_on_boot_or_restart()
    assert len(recovered) == 1
    assert recovered[0].task_id == "task_crash_01"
