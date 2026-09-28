"""PIXEL — Phase 17 Fleet Edge Resource & Battery Governor.

Enforces CPU/RAM/VRAM ceilings, battery conservation thresholds, thermal limits,
and task concurrency limits across edge devices.
"""

from packages.contracts.fleet import (
    EdgeNode,
    FleetCapability,
    ThermalState,
)


class FleetResourceGovernor:
    """Monitors edge node resource health and determines execution feasibility."""

    def __init__(
        self,
        min_battery_percent_for_heavy_tasks: float = 20.0,
        max_cpu_threshold: float = 85.0,
    ) -> None:
        self._min_battery_threshold = min_battery_percent_for_heavy_tasks
        self._max_cpu_threshold = max_cpu_threshold

    def can_accept_workload(
        self,
        node: EdgeNode,
        capability: FleetCapability,
        is_heavy_task: bool = False,
    ) -> tuple[bool, str | None]:
        """Evaluates whether an edge node has sufficient headroom to accept a workload."""
        # 1. Active task concurrency
        if node.resources.active_task_count >= node.resources.max_concurrent_tasks:
            return (
                False,
                f"Concurrency limit reached ({node.resources.active_task_count}/{node.resources.max_concurrent_tasks})",
            )

        # 2. Thermal health
        if node.resources.thermal_state == ThermalState.CRITICAL:
            return False, "Node in critical thermal state"
        if node.resources.thermal_state == ThermalState.THROTTLED and is_heavy_task:
            return False, "Node thermally throttled for heavy tasks"

        # 3. CPU Headroom
        if node.resources.cpu_usage_percent > self._max_cpu_threshold:
            return False, f"CPU usage exceeds threshold ({node.resources.cpu_usage_percent:.1f}%)"

        # 4. Battery conservation
        if (
            is_heavy_task
            and node.resources.battery_level_percent is not None
            and not node.resources.is_charging
            and node.resources.battery_level_percent < self._min_battery_threshold
        ):
            return (
                False,
                f"Battery too low ({node.resources.battery_level_percent:.1f}%) for heavy edge execution",
            )

        # 5. Capability-specific memory checks
        if capability in (FleetCapability.LOCAL_LLM, FleetCapability.LOCAL_VISION):
            if node.resources.ram_free_mb < 512:
                return False, f"Insufficient free RAM ({node.resources.ram_free_mb}MB)"

        return True, None
