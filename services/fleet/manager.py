"""PIXEL — Phase 17 Fleet Operations Manager Facade.

Master coordinator for all Edge AI Swarm, fleet discovery, multi-signal routing,
task delegation, distributed memory, kill switches, and failure recovery capabilities.
"""

from typing import Any

from packages.contracts.fleet import (
    DelegatedTaskEnvelope,
    FleetCapability,
    FleetDataClassification,
    FleetKillSwitchDomain,
    HardwareProfile,
    RoutingDecision,
    TaskLease,
)
from services.fleet.distributed_memory import FleetMemoryCoordinator
from services.fleet.failure_recovery import FleetFailureRecoveryEngine
from services.fleet.kill_switches import FleetKillSwitchManager
from services.fleet.mission_governor import AutonomousFleetMissionGovernor
from services.fleet.model_registry import FleetModelRegistry
from services.fleet.multimodal_edge import EdgeMultimodalCoordinator
from services.fleet.node_manager import EdgeNodeManager
from services.fleet.resource_governor import FleetResourceGovernor
from services.fleet.routing_engine import FleetRoutingEngine
from services.fleet.scheduler import FleetScheduler
from services.fleet.tools import (
    CancelFleetTaskTool,
    DelegateFleetTaskTool,
    DiscoverNodeCapabilitiesTool,
    GetFleetTopologyTool,
    RevokeFleetNodeTool,
)
from services.memory.manager import MemoryManager
from services.multimodal.manager import MultimodalPerceptionManager
from services.orchestration.pki import PKIEngine


class FleetOperationsManager:
    """Master manager for Phase 17 Edge AI Swarm Deployment & Fleet Operations."""

    def __init__(
        self,
        pki_engine: PKIEngine | None = None,
        memory_manager: MemoryManager | None = None,
        multimodal_manager: MultimodalPerceptionManager | None = None,
    ) -> None:
        self._pki_engine = pki_engine or PKIEngine()
        self._memory_manager = memory_manager
        self._multimodal_manager = multimodal_manager or MultimodalPerceptionManager()

        # 1. Fleet Core Subsystems
        self._node_manager = EdgeNodeManager(pki_engine=self._pki_engine)
        self._model_registry = FleetModelRegistry(pki_engine=self._pki_engine)
        self._resource_governor = FleetResourceGovernor()
        self._routing_engine = FleetRoutingEngine(
            node_manager=self._node_manager,
            resource_governor=self._resource_governor,
        )
        self._scheduler = FleetScheduler(node_manager=self._node_manager)
        self._memory_coordinator = FleetMemoryCoordinator(memory_manager=self._memory_manager)
        self._edge_multimodal = EdgeMultimodalCoordinator(
            node_manager=self._node_manager,
            routing_engine=self._routing_engine,
            local_multimodal=self._multimodal_manager,
        )
        self._failure_recovery = FleetFailureRecoveryEngine(
            node_manager=self._node_manager,
            scheduler=self._scheduler,
        )
        self._kill_switches = FleetKillSwitchManager()
        self._mission_governor = AutonomousFleetMissionGovernor()

        # 2. Register Central Authority Desktop Node
        self._seed_central_authority_node()

        # 3. Initialize L5 Tools
        self._tools = [
            GetFleetTopologyTool(self._node_manager),
            DiscoverNodeCapabilitiesTool(self._node_manager),
            DelegateFleetTaskTool(self._routing_engine, self._scheduler),
            CancelFleetTaskTool(self._scheduler),
            RevokeFleetNodeTool(self._node_manager),
        ]

    def _seed_central_authority_node(self) -> None:
        """Enrolls the primary central desktop authority node into the fleet."""
        self._node_manager.enroll_node(
            node_id="primary_desktop_core",
            node_name="PIXEL Primary Desktop Core",
            device_type="DESKTOP",
            capabilities=[
                FleetCapability.CPU,
                FleetCapability.GPU,
                FleetCapability.LOCAL_LLM,
                FleetCapability.LOCAL_VISION,
                FleetCapability.LOCAL_STT,
                FleetCapability.LOCAL_TTS,
                FleetCapability.BROWSER,
                FleetCapability.TERMINAL,
                FleetCapability.FILESYSTEM,
                FleetCapability.GIT,
                FleetCapability.MEMORY,
                FleetCapability.RAG,
            ],
            hardware=HardwareProfile(
                cpu_cores=16,
                has_gpu=True,
                gpu_name="NVIDIA RTX 4090",
                total_ram_mb=65536,
                total_vram_mb=24576,
            ),
            is_central_authority=True,
        )

    # --- Property Accessors ---
    @property
    def node_manager(self) -> EdgeNodeManager:
        return self._node_manager

    @property
    def model_registry(self) -> FleetModelRegistry:
        return self._model_registry

    @property
    def resource_governor(self) -> FleetResourceGovernor:
        return self._resource_governor

    @property
    def routing_engine(self) -> FleetRoutingEngine:
        return self._routing_engine

    @property
    def scheduler(self) -> FleetScheduler:
        return self._scheduler

    @property
    def memory_coordinator(self) -> FleetMemoryCoordinator:
        return self._memory_coordinator

    @property
    def edge_multimodal(self) -> EdgeMultimodalCoordinator:
        return self._edge_multimodal

    @property
    def failure_recovery(self) -> FleetFailureRecoveryEngine:
        return self._failure_recovery

    @property
    def kill_switches(self) -> FleetKillSwitchManager:
        return self._kill_switches

    @property
    def mission_governor(self) -> AutonomousFleetMissionGovernor:
        return self._mission_governor

    @property
    def tools(self) -> list[Any]:
        return self._tools

    # --- High-Level Delegation Flow ---
    def delegate_task(
        self,
        goal_description: str,
        capability: FleetCapability,
        source_node_id: str,
        data_classification: FleetDataClassification = FleetDataClassification.LOW_SENSITIVITY,
        is_heavy_task: bool = False,
    ) -> tuple[DelegatedTaskEnvelope, TaskLease, RoutingDecision]:
        """Calculates routing, creates signed delegation envelope, and grants exclusive lease."""
        # 1. Check Kill Switch
        if self._kill_switches.is_blocked(FleetKillSwitchDomain.AUTONOMOUS_DELEGATION):
            raise PermissionError("Autonomous task delegation is blocked by fleet kill switch.")

        # 2. Route
        decision = self._routing_engine.route_task(
            task_id="delegated_task_01",
            required_capability=capability,
            source_node_id=source_node_id,
            data_classification=data_classification,
            is_heavy_task=is_heavy_task,
        )

        # 3. Envelope
        envelope = self._scheduler.create_delegation_envelope(
            goal_description=goal_description,
            capability_required=capability,
            source_node_id=source_node_id,
            target_node_id=decision.selected_node_id,
            data_classification=data_classification,
        )

        # 4. Lease
        lease = self._scheduler.grant_lease(
            task_id=envelope.task_id, node_id=decision.selected_node_id
        )
        return envelope, lease, decision
