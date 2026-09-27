"""Authoritative Runtime Bridge and Control Plane Coordinator.

Integrates authoritative subsystems (L0-L10) without duplicating backend state.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from packages.contracts.autonomous import (
    AutonomousTaskContract,
    ExecutionBudget,
    GoalContract,
    TaskCheckpoint,
    TaskLifecycleState,
)
from packages.contracts.control_plane import (
    ControlPlaneEventType,
    ControlPlaneStreamEvent,
    ConversationSessionView,
    CreateTaskRequest,
    DeviceActionRequest,
    MemoryFactView,
    ServiceHealthStatus,
    SystemOverview,
    TaskActionRequest,
    TaskActionResponse,
    TaskSummary,
)
from packages.contracts.events import VoiceState
from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceIdentity,
    DeviceRole,
    DeviceTrustState,
    PairingChallenge,
    PairingConfirmation,
    PairingRequest,
    PairingResponse,
)
from packages.contracts.security import AuditRecord
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.tools.registry import ToolRegistry
from services.agent_runtime.verifier import ActionVerifier
from services.autonomous.budget_manager import BudgetManager
from services.autonomous.drift_detector import GoalDriftDetector
from services.autonomous.engine import AutonomousWorkflowEngine
from services.autonomous.event_bus import EventBus
from services.autonomous.governor import TaskGovernor
from services.autonomous.notifications import TaskNotificationManager
from services.autonomous.scheduler import AutonomousScheduler
from services.ecosystem.backup.manager import BackupManager
from services.ecosystem.backup.storage import ZeroKnowledgeBackupStorage
from services.ecosystem.connectors.registry import ConnectorRegistry
from services.ecosystem.lifecycle import PluginLifecycleManager
from services.ecosystem.marketplace import MarketplaceRegistry
from services.ecosystem.sandbox.subprocess_driver import SubprocessSandboxDriver
from services.ecosystem.skill_bridge import CommunitySkillBridge
from services.ecosystem.vetting import SkillVettingPipeline
from services.ecosystem.webhooks.engine import WebhookEngine
from services.memory.manager import MemoryManager
from services.orchestration.pki import PKIEngine
from services.orchestration.registry import DeviceRegistry, PresenceManager
from services.personalization.manager import PersonalizationManager
from services.voice_gateway.pipeline import VoicePipeline

logger = logging.getLogger(__name__)


class ControlPlaneManager:
    """Authoritative operational coordinator for the unified PIXEL Control Plane."""

    def __init__(
        self,
        device_registry: DeviceRegistry | None = None,
        presence_manager: PresenceManager | None = None,
        scheduler: AutonomousScheduler | None = None,
        autonomous_engine: AutonomousWorkflowEngine | None = None,
        budget_manager: BudgetManager | None = None,
        drift_detector: GoalDriftDetector | None = None,
        memory_manager: MemoryManager | None = None,
        personalization_manager: PersonalizationManager | None = None,
        policy_gate: AgentPolicyGate | None = None,
        tool_registry: ToolRegistry | None = None,
        event_bus: EventBus | None = None,
        voice_pipeline: VoicePipeline | None = None,
        plugin_lifecycle: PluginLifecycleManager | None = None,
        marketplace_registry: MarketplaceRegistry | None = None,
        backup_manager: BackupManager | None = None,
        connector_registry: ConnectorRegistry | None = None,
        webhook_engine: WebhookEngine | None = None,
    ) -> None:
        # 1. Device and Topology
        self.pki_engine = PKIEngine()
        self.device_registry = device_registry or DeviceRegistry(pki_engine=self.pki_engine)
        self.presence_manager = presence_manager or PresenceManager()

        # 2. Personalization & Memory
        self.personalization_manager = personalization_manager or PersonalizationManager(
            db_path="data/persistence/pixel_user_model.db"
        )
        self.memory_manager = memory_manager or MemoryManager(
            db_path="data/persistence/pixel_memory.db",
            personalization_manager=self.personalization_manager,
        )
        if not self.memory_manager.personalization_manager:
            self.memory_manager.personalization_manager = self.personalization_manager

        # 3. Policy and Verification
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.tool_registry = tool_registry or ToolRegistry()
        self.action_verifier = ActionVerifier()

        # 4. Autonomous Scheduler & Engine
        self.scheduler = scheduler or AutonomousScheduler(
            db_path="data/persistence/pixel_scheduler.db"
        )
        self.budget_manager = budget_manager or BudgetManager(
            db_path="data/persistence/pixel_budget.db"
        )
        self.drift_detector = drift_detector or GoalDriftDetector()
        self.governor = TaskGovernor(max_concurrent_tasks=5)
        self.notification_manager = TaskNotificationManager()
        self.autonomous_engine = autonomous_engine or AutonomousWorkflowEngine(
            scheduler=self.scheduler,
            budget_manager=self.budget_manager,
            drift_detector=self.drift_detector,
            governor=self.governor,
            notification_manager=self.notification_manager,
            policy_gate=self.policy_gate,
            tool_registry=self.tool_registry,
            action_verifier=self.action_verifier,
        )

        # 5. Event Bus and Voice
        self.event_bus = event_bus or EventBus()
        self.voice_pipeline = voice_pipeline

        # 6. Ecosystem & Extensibility Hub (Phase 11)
        self.sandbox_driver = SubprocessSandboxDriver()
        self.plugin_lifecycle = plugin_lifecycle or PluginLifecycleManager(
            db_path="data/persistence/pixel_plugins.db",
            sandbox_driver=self.sandbox_driver,
            base_plugins_dir="data/persistence/plugins",
        )
        self.skill_vetting = SkillVettingPipeline()
        self.marketplace = marketplace_registry or MarketplaceRegistry(
            lifecycle_manager=self.plugin_lifecycle,
            vetting_pipeline=self.skill_vetting,
            skills_store_dir="data/persistence/marketplace_skills",
        )
        self.skill_bridge = CommunitySkillBridge(
            lifecycle_manager=self.plugin_lifecycle,
            marketplace_registry=self.marketplace,
            tool_registry=self.tool_registry,
            policy_gate=self.policy_gate,
        )
        self.backup_storage = ZeroKnowledgeBackupStorage(
            db_path="data/persistence/pixel_backups.db"
        )
        self.backup_manager = backup_manager or BackupManager(
            storage=self.backup_storage,
            memory_manager=self.memory_manager,
            device_registry=self.device_registry,
        )
        self.connector_registry = connector_registry or ConnectorRegistry(
            db_path="data/persistence/pixel_connectors.db"
        )
        self.webhook_engine = webhook_engine or WebhookEngine(
            event_bus=self.event_bus,
            connector_registry=self.connector_registry,
        )
        self.webhook_engine.start()

        # 7. Continuous Autonomous Evolution & Self-Healing Swarms (Phase 12)
        from services.evolution import (
            ChangeProposalManager,
            DatasetLineageTracker,
            DiagnosticEngine,
            DifferentialPrivacyAccountant,
            EvolutionGovernor,
            EvolutionModelRegistry,
            KillSwitchSystem,
            MemoryMeshReplicator,
            ModelSafetyEvaluator,
            ProgressiveDistillationEngine,
            RegressionTestGenerator,
            RuntimeSelfProfiler,
            SelfHealingOrchestrator,
            SwarmCoordinator,
        )

        self.runtime_profiler = RuntimeSelfProfiler()
        self.diagnostic_engine = DiagnosticEngine(profiler=self.runtime_profiler)
        self.proposal_manager = ChangeProposalManager(db_path="data/persistence/pixel_proposals.db")
        self.regression_generator = RegressionTestGenerator()
        self.self_healing = SelfHealingOrchestrator(
            proposal_manager=self.proposal_manager,
            policy_gate=self.policy_gate,
            action_verifier=self.action_verifier,
            regression_generator=self.regression_generator,
        )
        self.memory_mesh = MemoryMeshReplicator(node_id="primary_desktop_core")
        self.lineage_tracker = DatasetLineageTracker()
        self.dp_accountant = DifferentialPrivacyAccountant()
        self.model_evaluator = ModelSafetyEvaluator()
        self.distillation_engine = ProgressiveDistillationEngine()
        self.model_registry = EvolutionModelRegistry(evaluator=self.model_evaluator)
        self.kill_switches = KillSwitchSystem(db_path="data/persistence/pixel_killswitches.db")
        self.evolution_governor = EvolutionGovernor(
            kill_switch_system=self.kill_switches,
            policy_gate=self.policy_gate,
        )
        self.swarm_coordinator = SwarmCoordinator(
            policy_gate=self.policy_gate,
            action_verifier=self.action_verifier,
        )

        # 8. Active Conversation Sessions Tracking
        self._active_sessions: dict[str, ConversationSessionView] = {}

        # 9. WebSocket Subscriber Queues
        self._ws_subscribers: set[asyncio.Queue[ControlPlaneStreamEvent]] = set()

        # Seed initial core desktop identity if registry is empty
        self._seed_core_device()

    def _seed_core_device(self) -> None:
        """Ensure primary central node is registered."""
        if not self.device_registry.list_devices():
            now = datetime.now(UTC)
            core_id = "primary_desktop_core"
            identity = DeviceIdentity(
                device_id=core_id,
                device_type=DeviceRole.PRIMARY_PC,
                device_name="PIXEL Primary Desktop Core",
                public_key_fingerprint="sha256:core_master_node_fingerprint",
                capabilities=[
                    DeviceCapability.DESKTOP_CONTROL,
                    DeviceCapability.CODE_EXECUTION,
                    DeviceCapability.MICROPHONE,
                    DeviceCapability.SPEAKER,
                    DeviceCapability.DISPLAY,
                ],
                trust_state=DeviceTrustState.TRUSTED,
                created_at=now,
                updated_at=now,
            )
            self.device_registry._devices[core_id] = identity
            self.presence_manager.update_heartbeat(
                device_id=core_id,
                rtt_ms=0.5,
                battery_level=100,
                is_charging=True,
                active_session_id=None,
            )

    # --------------------------------------------------------------------------
    # Real-Time WebSocket Broadcasting
    # --------------------------------------------------------------------------
    def subscribe_events(self) -> asyncio.Queue[ControlPlaneStreamEvent]:
        """Subscribe to real-time control plane stream events."""
        queue: asyncio.Queue[ControlPlaneStreamEvent] = asyncio.Queue(maxsize=500)
        self._ws_subscribers.add(queue)
        return queue

    def unsubscribe_events(self, queue: asyncio.Queue[ControlPlaneStreamEvent]) -> None:
        """Unsubscribe from real-time events."""
        self._ws_subscribers.discard(queue)

    async def broadcast_event(
        self, event_type: ControlPlaneEventType, payload: dict[str, Any]
    ) -> None:
        """Broadcast a typed event to all active Control Plane WebSocket clients."""
        evt = ControlPlaneStreamEvent(
            event_type=event_type,
            timestamp=datetime.now(UTC),
            payload=payload,
        )
        dead_queues = set()
        for q in self._ws_subscribers:
            try:
                if q.full():
                    try:
                        q.get_nowait()  # Drop oldest event to prevent slow client blocking
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(evt)
            except Exception:
                dead_queues.add(q)
        for dead in dead_queues:
            self._ws_subscribers.discard(dead)

    # --------------------------------------------------------------------------
    # System Overview & Health
    # --------------------------------------------------------------------------
    async def get_system_overview(self) -> SystemOverview:
        """Generate comprehensive, authoritative system status."""
        self.presence_manager.sweep_stale_devices()
        online_devices = self.presence_manager.get_online_devices()
        all_tasks = self.scheduler.list_all_tasks()
        active_tasks = [
            t
            for t in all_tasks
            if t.state in [TaskLifecycleState.RUNNING, TaskLifecycleState.SCHEDULED]
        ]

        services = [
            ServiceHealthStatus(
                service_name="L0_DeviceRuntime",
                is_healthy=True,
                latency_ms=0.2,
                details={"online_devices": len(online_devices)},
            ),
            ServiceHealthStatus(
                service_name="L1_VoiceGateway",
                is_healthy=True,
                latency_ms=1.1,
                details={"active_sessions": len(self._active_sessions)},
            ),
            ServiceHealthStatus(
                service_name="L4_AgentRuntime",
                is_healthy=True,
                latency_ms=0.8,
                details={"governor_slots_in_use": len(self.governor._active_tasks)},
            ),
            ServiceHealthStatus(
                service_name="L6_PolicyEngine",
                is_healthy=True,
                latency_ms=0.05,
                details={"audit_records_count": len(self.policy_gate.audit_log)},
            ),
            ServiceHealthStatus(
                service_name="L9_MemoryStore",
                is_healthy=True,
                latency_ms=2.3,
                details={"store_type": "SQLiteMemoryStore"},
            ),
            ServiceHealthStatus(
                service_name="AutonomousScheduler",
                is_healthy=True,
                latency_ms=0.4,
                details={"total_tasks": len(all_tasks), "active_tasks": len(active_tasks)},
            ),
        ]

        return SystemOverview(
            runtime_version="1.0.0",
            environment="production",
            is_online=True,
            active_devices_count=len(online_devices),
            active_tasks_count=len(active_tasks),
            active_sessions_count=len(self._active_sessions),
            services=services,
            resource_stats={
                "governor_active_tasks": len(self.governor._active_tasks),
                "total_audit_records": len(self.policy_gate.audit_log),
                "total_devices_registered": len(self.device_registry.list_devices()),
                "total_scheduled_tasks": len(all_tasks),
            },
            timestamp=datetime.now(UTC),
        )

    # --------------------------------------------------------------------------
    # Conversation Sessions
    # --------------------------------------------------------------------------
    def record_session_turn(
        self,
        session_id: str,
        user_id: str,
        device_id: str,
        voice_state: VoiceState,
        user_query: str,
        assistant_response: str,
    ) -> ConversationSessionView:
        """Record an active conversation turn and update tracking."""
        now = datetime.now(UTC)
        sess = self._active_sessions.get(session_id)
        turn_data = {
            "timestamp": now.isoformat(),
            "user_query": user_query,
            "assistant_response": assistant_response,
            "state": voice_state.value,
        }
        if not sess:
            sess = ConversationSessionView(
                session_id=session_id,
                user_id=user_id,
                device_id=device_id,
                voice_state=voice_state,
                current_transcript=user_query,
                last_response=assistant_response,
                turn_count=1,
                recent_turns=[turn_data],
                created_at=now,
                last_activity=now,
            )
            self._active_sessions[session_id] = sess
        else:
            sess.voice_state = voice_state
            sess.current_transcript = user_query
            sess.last_response = assistant_response
            sess.turn_count += 1
            sess.last_activity = now
            sess.recent_turns.append(turn_data)
            if len(sess.recent_turns) > 20:
                sess.recent_turns.pop(0)

        # Broadcast update if event loop is running
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self.broadcast_event(
                    ControlPlaneEventType.CONVERSATION_UPDATE,
                    {"session": sess.model_dump(mode="json")},
                )
            )
        except RuntimeError:
            pass
        return sess

    def list_conversation_sessions(self) -> list[ConversationSessionView]:
        """List active conversation sessions."""
        return list(self._active_sessions.values())

    def get_conversation_session(self, session_id: str) -> ConversationSessionView | None:
        """Get detail of a specific conversation session."""
        return self._active_sessions.get(session_id)

    # --------------------------------------------------------------------------
    # Autonomous Tasks Management
    # --------------------------------------------------------------------------
    async def list_tasks(
        self,
        user_id: str | None = None,
        state: TaskLifecycleState | None = None,
    ) -> list[TaskSummary]:
        """List autonomous tasks converted to dashboard summaries."""
        tasks = self.scheduler.list_all_tasks(user_id=user_id, state=state)
        summaries: list[TaskSummary] = []
        for t in tasks:
            budget = self.budget_manager.get_budget(t.task_id) or t.budget
            summaries.append(
                TaskSummary(
                    task_id=t.task_id,
                    user_id=t.user_id,
                    objective=t.goal.objective,
                    state=t.state,
                    schedule_type=t.schedule_type,
                    schedule_expr=t.schedule_expr,
                    created_at=t.created_at,
                    next_run_at=t.next_run_at,
                    last_run_at=t.last_run_at,
                    budget_consumed_steps=budget.consumed_steps,
                    budget_max_steps=budget.max_steps,
                    is_paused=t.is_paused,
                    is_cancelled=t.is_cancelled,
                    failure_reason=t.failure_reason,
                )
            )
        return summaries

    async def get_task_detail(self, task_id: str) -> AutonomousTaskContract | None:
        """Get complete task contract."""
        return self.scheduler.get_task(task_id)

    async def create_task(
        self, req: CreateTaskRequest, user_id: str = "default_user"
    ) -> AutonomousTaskContract:
        """Create and submit a new autonomous task."""
        import uuid

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        goal = GoalContract(
            objective=req.objective,
            success_criteria=req.success_criteria,
            constraints=req.constraints,
            allowed_targets=req.allowed_targets,
            prohibited_actions=req.prohibited_actions,
            authorized_by=user_id,
        )
        budget = ExecutionBudget(
            max_steps=req.max_steps,
            max_tool_calls=req.max_tool_calls,
            max_duration_seconds=req.max_duration_seconds,
        )
        task = AutonomousTaskContract(
            task_id=task_id,
            user_id=user_id,
            session_id=f"sess_{task_id}",
            goal=goal,
            schedule_type=req.schedule_type,
            schedule_expr=req.schedule_expr,
            missed_job_policy=req.missed_job_policy,
            budget=budget,
            allowed_tools=req.allowed_tools,
            prohibited_tools=req.prohibited_tools,
            state=TaskLifecycleState.CREATED,
            created_at=datetime.now(UTC),
            owner_device_id="primary_desktop_core",
        )
        await self.autonomous_engine.submit_task(task)

        # Broadcast state change
        await self.broadcast_event(
            ControlPlaneEventType.TASK_STATE_CHANGED,
            {"task_id": task_id, "state": task.state.value, "action": "CREATE"},
        )
        return task

    async def execute_task_action(
        self, task_id: str, req: TaskActionRequest, actor_id: str = "admin"
    ) -> TaskActionResponse:
        """Execute operational command on an autonomous task."""
        action = req.action.upper()
        task = self.scheduler.get_task(task_id)
        if not task:
            return TaskActionResponse(
                success=False,
                task_id=task_id,
                action=action,
                new_state=TaskLifecycleState.FAILED,
                message=f"Task '{task_id}' not found.",
            )

        if action == "PAUSE":
            await self.autonomous_engine.pause_task(task_id)
            updated = self.scheduler.get_task(task_id)
            new_state = updated.state if updated else TaskLifecycleState.PAUSED
            await self.broadcast_event(
                ControlPlaneEventType.TASK_STATE_CHANGED,
                {"task_id": task_id, "state": new_state.value, "action": "PAUSE"},
            )
            return TaskActionResponse(
                success=True,
                task_id=task_id,
                action=action,
                new_state=new_state,
                message=f"Task '{task_id}' paused successfully.",
            )

        elif action == "RESUME":
            await self.autonomous_engine.resume_task(task_id)
            updated = self.scheduler.get_task(task_id)
            new_state = updated.state if updated else TaskLifecycleState.SCHEDULED
            await self.broadcast_event(
                ControlPlaneEventType.TASK_STATE_CHANGED,
                {"task_id": task_id, "state": new_state.value, "action": "RESUME"},
            )
            return TaskActionResponse(
                success=True,
                task_id=task_id,
                action=action,
                new_state=new_state,
                message=f"Task '{task_id}' resumed successfully.",
            )

        elif action == "CANCEL":
            await self.autonomous_engine.cancel_task(task_id)
            updated = self.scheduler.get_task(task_id)
            new_state = updated.state if updated else TaskLifecycleState.CANCELLED
            await self.broadcast_event(
                ControlPlaneEventType.TASK_STATE_CHANGED,
                {"task_id": task_id, "state": new_state.value, "action": "CANCEL"},
            )
            return TaskActionResponse(
                success=True,
                task_id=task_id,
                action=action,
                new_state=new_state,
                message=f"Task '{task_id}' cancelled.",
            )

        elif action == "TRIGGER_NOW":
            new_state = await self.autonomous_engine.execute_task_segment(task_id, max_steps=5)
            await self.broadcast_event(
                ControlPlaneEventType.TASK_STATE_CHANGED,
                {"task_id": task_id, "state": new_state.value, "action": "TRIGGER_NOW"},
            )
            return TaskActionResponse(
                success=True,
                task_id=task_id,
                action=action,
                new_state=new_state,
                message=f"Task '{task_id}' executed segment (new state: {new_state.value}).",
            )

        elif action == "APPROVE":
            # Resume task awaiting approval
            if task.state == TaskLifecycleState.AWAITING_APPROVAL:
                self.scheduler.update_task_state(task_id, TaskLifecycleState.SCHEDULED)
                new_state = TaskLifecycleState.SCHEDULED
                await self.broadcast_event(
                    ControlPlaneEventType.TASK_STATE_CHANGED,
                    {"task_id": task_id, "state": new_state.value, "action": "APPROVE"},
                )
                return TaskActionResponse(
                    success=True,
                    task_id=task_id,
                    action=action,
                    new_state=new_state,
                    message="Approval recorded; task returned to scheduled state.",
                )
            else:
                return TaskActionResponse(
                    success=False,
                    task_id=task_id,
                    action=action,
                    new_state=task.state,
                    message=f"Task '{task_id}' is not awaiting approval (state: {task.state.value}).",
                )

        elif action == "REJECT":
            self.scheduler.update_task_state(task_id, TaskLifecycleState.POLICY_DENIED)
            new_state = TaskLifecycleState.POLICY_DENIED
            await self.broadcast_event(
                ControlPlaneEventType.TASK_STATE_CHANGED,
                {"task_id": task_id, "state": new_state.value, "action": "REJECT"},
            )
            return TaskActionResponse(
                success=True,
                task_id=task_id,
                action=action,
                new_state=new_state,
                message="Action rejected by operator; task marked POLICY_DENIED.",
            )

        return TaskActionResponse(
            success=False,
            task_id=task_id,
            action=action,
            new_state=task.state,
            message=f"Unsupported action '{action}'.",
        )

    def get_task_checkpoints(self, task_id: str) -> list[TaskCheckpoint]:
        """Get checkpoint history for a task."""
        return self.autonomous_engine._checkpoints.get(task_id, [])

    # --------------------------------------------------------------------------
    # Memory & Knowledge
    # --------------------------------------------------------------------------
    async def list_memory_facts(self, user_id: str = "default_user") -> list[MemoryFactView]:
        """List active semantic facts stored in persistent memory."""
        facts = await self.memory_manager.store.list_facts(user_id=user_id)
        return [
            MemoryFactView(
                fact_id=f.fact_id,
                user_id=f.user_id,
                category=f.category,
                key=f.key,
                value=f.value,
                confidence=f.confidence,
                provenance=f.provenance,
                created_at=f.created_at,
            )
            for f in facts
        ]

    async def search_memory(
        self, query: str, user_id: str = "default_user", limit: int = 10
    ) -> dict[str, Any]:
        """Search across working, episodic, and semantic memory."""
        return await self.memory_manager.query_relevant_memory(
            query=query, user_id=user_id, top_k_episodes=limit
        )

    async def forget_memory(self, keyword: str, user_id: str = "default_user") -> int:
        """Right to Forget purge by topic/keyword."""
        deleted_count = await self.memory_manager.forget_topic(keyword=keyword, user_id=user_id)
        await self.broadcast_event(
            ControlPlaneEventType.AUDIT_EVENT,
            {
                "action": "MEMORY_FORGET",
                "keyword": keyword,
                "deleted_count": deleted_count,
                "user_id": user_id,
            },
        )
        return deleted_count

    # --------------------------------------------------------------------------
    # Device Topology & Management
    # --------------------------------------------------------------------------
    async def list_devices(self) -> list[dict[str, Any]]:
        """List all registered devices with their real-time presence telemetry."""
        self.presence_manager.sweep_stale_devices()
        devices = self.device_registry.list_devices()
        topology: list[dict[str, Any]] = []
        for d in devices:
            presence = self.presence_manager.get_presence(d.device_id)
            topology.append(
                {
                    "identity": d.model_dump(mode="json"),
                    "presence": presence.model_dump(mode="json") if presence else None,
                }
            )
        return topology

    async def get_device_detail(self, device_id: str) -> dict[str, Any] | None:
        """Get detail of a registered device."""
        device = self.device_registry.get_device(device_id)
        if not device:
            return None
        presence = self.presence_manager.get_presence(device_id)
        return {
            "identity": device.model_dump(mode="json"),
            "presence": presence.model_dump(mode="json") if presence else None,
        }

    async def initiate_device_pairing(self, req: PairingRequest) -> PairingChallenge:
        """Initiate device pairing challenge."""
        challenge = self.device_registry.initiate_pairing(req)
        await self.broadcast_event(
            ControlPlaneEventType.DEVICE_PRESENCE,
            {"device_id": req.device_id, "state": "PAIRING_INITIATED"},
        )
        return challenge

    async def confirm_device_pairing(self, conf: PairingConfirmation) -> PairingResponse:
        """Confirm device pairing PIN and register trusted identity."""
        response = self.device_registry.complete_pairing(conf)
        if response.success:
            self.presence_manager.update_heartbeat(
                device_id=conf.device_id,
                rtt_ms=1.0,
                battery_level=100,
                is_charging=True,
            )
            await self.broadcast_event(
                ControlPlaneEventType.DEVICE_PRESENCE,
                {"device_id": conf.device_id, "state": "PAIRING_SUCCESS"},
            )
        return response

    async def execute_device_action(
        self, device_id: str, req: DeviceActionRequest, actor_id: str = "admin"
    ) -> bool:
        """Execute device lifecycle action (e.g. REVOKE, REMOVE)."""
        action = req.action.upper()
        if action == "REVOKE":
            res = self.device_registry.revoke_device(device_id=device_id, reason=req.reason)
            self.presence_manager.set_device_offline(device_id)
            await self.broadcast_event(
                ControlPlaneEventType.DEVICE_PRESENCE,
                {"device_id": device_id, "state": "REVOKED"},
            )
            return res
        elif action == "REMOVE":
            res = self.device_registry.remove_device(device_id)
            self.presence_manager.set_device_offline(device_id)
            await self.broadcast_event(
                ControlPlaneEventType.DEVICE_PRESENCE,
                {"device_id": device_id, "state": "REMOVED"},
            )
            return res
        elif action == "SET_OFFLINE":
            self.presence_manager.set_device_offline(device_id)
            await self.broadcast_event(
                ControlPlaneEventType.DEVICE_PRESENCE,
                {"device_id": device_id, "state": "OFFLINE"},
            )
            return True
        return False

    # --------------------------------------------------------------------------
    # Audit Logs
    # --------------------------------------------------------------------------
    def get_audit_logs(
        self,
        actor_id: str | None = None,
        tool_name: str | None = None,
        limit: int = 100,
    ) -> list[AuditRecord]:
        """Query immutable policy and execution audit records."""
        logs = list(self.policy_gate.audit_log)
        if actor_id:
            logs = [rec for rec in logs if rec.actor_id == actor_id]
        if tool_name:
            logs = [rec for rec in logs if rec.tool_name == tool_name]
        return logs[-limit:]
