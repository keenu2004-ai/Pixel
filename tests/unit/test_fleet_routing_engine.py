"""Unit tests for FleetRoutingEngine."""

from packages.contracts.fleet import (
    FleetCapability,
    FleetDataClassification,
    HardwareProfile,
    NetworkCondition,
    ResourceProfile,
    ThermalState,
)
from services.fleet.node_manager import EdgeNodeManager
from services.fleet.resource_governor import FleetResourceGovernor
from services.fleet.routing_engine import FleetRoutingEngine


def test_multi_signal_routing() -> None:
    """Verify routing decisions considering capabilities, privacy, battery, network, and resource constraints."""
    node_mgr = EdgeNodeManager()
    gov = FleetResourceGovernor()
    engine = FleetRoutingEngine(node_manager=node_mgr, resource_governor=gov)

    # 1. Enroll Central Desktop
    node_mgr.enroll_node(
        node_id="primary_desktop_core",
        node_name="Central Desktop",
        device_type="DESKTOP",
        capabilities=[
            FleetCapability.CPU,
            FleetCapability.GPU,
            FleetCapability.LOCAL_LLM,
            FleetCapability.LOCAL_VISION,
        ],
        hardware=HardwareProfile(cpu_cores=16, total_ram_mb=32768, has_gpu=True),
        is_central_authority=True,
    )

    # 2. Enroll Phone (Battery 85%)
    node_mgr.enroll_node(
        node_id="phone_pixel_01",
        node_name="Pixel Phone",
        device_type="PHONE",
        capabilities=[
            FleetCapability.MICROPHONE,
            FleetCapability.LOCAL_STT,
            FleetCapability.CAMERA,
        ],
        hardware=HardwareProfile(cpu_cores=8, total_ram_mb=12288),
    )

    # Test 1: Highly Sensitive Data -> Strict Local Requirement
    decision_sensitive = engine.route_task(
        task_id="task_otp_extract",
        required_capability=FleetCapability.LOCAL_STT,
        source_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.HIGHLY_SENSITIVE,
    )
    assert decision_sensitive.execution_tier == "LOCAL"
    assert decision_sensitive.selected_node_id == "phone_pixel_01"

    # Test 2: Heavy GPU Vision Task -> Remote Server/Desktop Placement
    decision_heavy = engine.route_task(
        task_id="task_screen_heavy",
        required_capability=FleetCapability.LOCAL_VISION,
        source_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.LOW_SENSITIVITY,
        is_heavy_task=True,
    )
    assert decision_heavy.selected_node_id == "primary_desktop_core"
    assert decision_heavy.execution_tier in ["REMOTE", "DISTRIBUTED"]

    # Test 3: Low Battery Offloading (<20%)
    node_mgr.record_heartbeat(
        "phone_pixel_01",
        resources=ResourceProfile(
            cpu_usage_percent=20.0,
            ram_free_mb=10288,
            battery_level_percent=14.0,  # Critical low battery!
            is_charging=False,
            thermal_state=ThermalState.NOMINAL,
            network_condition=NetworkCondition.EXCELLENT,
        ),
    )
    decision_battery = engine.route_task(
        task_id="task_compute",
        required_capability=FleetCapability.CPU,
        source_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.LOW_SENSITIVITY,
        is_heavy_task=True,
    )
    # Since battery is <20%, engine should offload to central desktop
    assert decision_battery.selected_node_id == "primary_desktop_core"
