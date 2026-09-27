"""Unit tests for MultiDeviceRuntime."""

import pytest

from packages.contracts.orchestration import DeviceRole, WakeArbitrationCandidate
from packages.contracts.runtime import CrossDeviceHandoffState
from services.orchestration.multi_device_runtime import MultiDeviceRuntime


@pytest.mark.asyncio
async def test_device_registration_and_wake_arbitration() -> None:
    runtime = MultiDeviceRuntime()

    # Register phone, pc, and satellite
    dev_phone = runtime.register_device("phone-01", DeviceRole.MOBILE_NODE, "Pixel 8 Pro")
    dev_pc = runtime.register_device("pc-01", DeviceRole.PRIMARY_PC, "Workstation PC")
    dev_sat = runtime.register_device(
        "sat-01", DeviceRole.SATELLITE_MIC_SPEAKER, "Living Room Speaker"
    )

    assert dev_phone.device_id == "phone-01"
    assert dev_pc.device_id == "pc-01"
    assert dev_sat.device_id == "sat-01"

    # Wake arbitration: phone hears with lower latency / higher confidence
    candidates = [
        WakeArbitrationCandidate(
            device_id="phone-01",
            wake_event_id="w-1",
            timestamp_ms=1000,
            confidence=0.98,
            rtt_ms=12.0,
        ),
        WakeArbitrationCandidate(
            device_id="sat-01",
            wake_event_id="w-1",
            timestamp_ms=1000,
            confidence=0.85,
            rtt_ms=45.0,
        ),
    ]
    res = runtime.arbitrate_wake_word(candidates)
    assert res.winner_device_id == "phone-01"
    assert "sat-01" in res.suppressed_device_ids


@pytest.mark.asyncio
async def test_cross_device_context_handoff() -> None:
    runtime = MultiDeviceRuntime()
    runtime.register_device("phone-01", DeviceRole.MOBILE_NODE)
    runtime.register_device("pc-01", DeviceRole.PRIMARY_PC)

    # Initiate handoff: Phone -> PC
    handoff = await runtime.initiate_handoff(
        origin_device_id="phone-01",
        target_device_id="pc-01",
        task_id="task_code_fix",
        session_id="sess_cross_01",
        user_id="user_v",
        context_data={"repo": "Pixel", "action": "run_pytest"},
    )
    assert handoff.state == CrossDeviceHandoffState.ROUTED

    # Complete handoff: PC finishes and responds
    res = await runtime.complete_handoff(
        handoff_id=handoff.handoff_id,
        result_payload={"test_results": "389 passed"},
        success=True,
    )
    assert res.success
    assert res.response_device_id == "pc-01"
    assert res.response_payload.get("test_results") == "389 passed"


@pytest.mark.asyncio
async def test_offline_degradation_and_network_recovery() -> None:
    runtime = MultiDeviceRuntime()
    runtime.register_device("phone-01", DeviceRole.MOBILE_NODE)
    runtime.register_device("pc-01", DeviceRole.PRIMARY_PC)

    # Go OFFLINE
    runtime.set_network_state(False)
    assert not runtime.is_online

    # Enqueue task while offline
    handoff = await runtime.initiate_handoff(
        origin_device_id="phone-01",
        target_device_id="pc-01",
        task_id="task_deferred",
        session_id="sess_offline",
        user_id="user_v",
        context_data={"cmd": "sync"},
    )
    assert handoff.state == CrossDeviceHandoffState.INITIATED
    assert len(runtime._offline_pending_queue) == 1

    # Network restored
    runtime.set_network_state(True)
    reconciled = runtime.reconcile_on_network_recovery()
    assert reconciled == 1
    assert len(runtime._offline_pending_queue) == 0
