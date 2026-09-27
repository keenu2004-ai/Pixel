"""Deterministic Intent Capability Router and Security Policy Dispatcher.

Routes parsed IntentPackets to registered ToolSpecs, enforces L6 Security Policies,
maintains idempotency tracking, logs audit records, and executes via OS Adapters.
"""

import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from packages.contracts.deterministic import (
    AlarmAction,
    AppAction,
    ReminderAction,
    SystemQueryType,
    TimerAction,
    VolumeAction,
)
from packages.contracts.intents import IntentPacket
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import (
    AuditLevel,
    RiskClass,
    ToolExecutionResult,
    ToolSpec,
)
from packages.core.interfaces.os_adapter import BaseOSAdapter
from packages.core.policy import PolicyEngine

logger = logging.getLogger(__name__)


class DeterministicRouter:
    """Dispatches deterministic intent packets through security policy checks to OS adapters."""

    def __init__(self, os_adapter: BaseOSAdapter) -> None:
        self.os_adapter = os_adapter
        self._tools: dict[str, ToolSpec] = {}
        self._idempotency_cache: dict[str, ToolExecutionResult] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Registers canonical OS tool specifications."""
        tools = [
            ToolSpec(
                name="set_timer",
                description="Starts a countdown timer for a specified duration in seconds.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={
                    "type": "object",
                    "properties": {"duration_seconds": {"type": "integer"}},
                },
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="cancel_timer",
                description="Cancels an active timer.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={
                    "type": "object",
                    "properties": {"timer_id": {"type": "string"}},
                },
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="get_timer_status",
                description="Queries status of active timer.",
                risk_class=RiskClass.READ,
                parameters_schema={"type": "object"},
                audit_level=AuditLevel.NONE,
            ),
            ToolSpec(
                name="set_alarm",
                description="Schedules a system alarm for a specific timestamp.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={
                    "type": "object",
                    "properties": {"target_time": {"type": "string"}},
                },
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="cancel_alarm",
                description="Cancels a scheduled alarm.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={
                    "type": "object",
                    "properties": {"alarm_id": {"type": "string"}},
                },
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="list_alarms",
                description="Lists all scheduled alarms.",
                risk_class=RiskClass.READ,
                parameters_schema={"type": "object"},
                audit_level=AuditLevel.NONE,
            ),
            ToolSpec(
                name="set_reminder",
                description="Creates a persistent reminder.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={"type": "object", "properties": {"text": {"type": "string"}}},
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="list_reminders",
                description="Lists all active reminders.",
                risk_class=RiskClass.READ,
                parameters_schema={"type": "object"},
                audit_level=AuditLevel.NONE,
            ),
            ToolSpec(
                name="cancel_reminder",
                description="Cancels an existing reminder.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={
                    "type": "object",
                    "properties": {"reminder_id": {"type": "string"}},
                },
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="set_volume",
                description="Sets master audio volume.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={"type": "object", "properties": {"level": {"type": "integer"}}},
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="adjust_volume",
                description="Increases or decreases audio volume.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={"type": "object", "properties": {"delta": {"type": "integer"}}},
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="mute_volume",
                description="Mutes system audio.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={"type": "object"},
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="unmute_volume",
                description="Unmutes system audio.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={"type": "object"},
                audit_level=AuditLevel.BASIC,
            ),
            ToolSpec(
                name="launch_app",
                description="Launches an approved application.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={
                    "type": "object",
                    "properties": {"app_name": {"type": "string"}},
                },
                audit_level=AuditLevel.DETAILED,
            ),
            ToolSpec(
                name="close_app",
                description="Closes an open application.",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={
                    "type": "object",
                    "properties": {"app_name": {"type": "string"}},
                },
                audit_level=AuditLevel.DETAILED,
            ),
            ToolSpec(
                name="get_system_time",
                description="Queries the current system time.",
                risk_class=RiskClass.READ,
                parameters_schema={"type": "object"},
                audit_level=AuditLevel.NONE,
            ),
            ToolSpec(
                name="get_battery_status",
                description="Queries device battery level and power status.",
                risk_class=RiskClass.READ,
                parameters_schema={"type": "object"},
                audit_level=AuditLevel.NONE,
            ),
        ]
        for t in tools:
            self._tools[t.name] = t

    def _compute_idempotency_key(
        self, tool_name: str, arguments: dict[str, Any], session_id: str | None
    ) -> str:
        """Computes a deterministic hash for idempotency deduplication."""
        raw_key = f"{session_id}:{tool_name}:{json.dumps(arguments, sort_keys=True, default=str)}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def execute_intent(
        self,
        packet: IntentPacket,
        is_user_confirmed: bool = False,
        idempotency_window_sec: float = 5.0,
    ) -> ToolExecutionResult:
        """Executes a parsed IntentPacket with policy evaluation and idempotency."""
        t0 = time.perf_counter()
        trace_id = packet.trace_id or uuid4().hex
        session_id = packet.session_id or "default"

        tool_name, arguments = self._resolve_tool_and_args(packet)
        if not tool_name or tool_name not in self._tools:
            return ToolExecutionResult(
                success=False,
                output=None,
                error=f"Unsupported or unrecognized deterministic intent: {packet.target_intent}",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )

        tool_spec = self._tools[tool_name]

        # 1. Idempotency check for write operations
        if tool_spec.risk_class != RiskClass.READ:
            idem_key = self._compute_idempotency_key(tool_name, arguments, session_id)
            if idem_key in self._idempotency_cache:
                logger.info(
                    "Idempotent request duplicate detected for key %s. Returning cached result.",
                    idem_key,
                )
                return self._idempotency_cache[idem_key]

        # 2. L6 Policy Engine Security Check
        decision = PolicyEngine.evaluate_tool_request(
            tool_spec=tool_spec,
            arguments=arguments,
            is_user_confirmed=is_user_confirmed,
        )

        if decision.verdict == PolicyVerdict.DENY:
            logger.warning(
                "Policy Engine denied execution for tool '%s': %s", tool_name, decision.reason
            )
            return ToolExecutionResult(
                success=False,
                output=None,
                error=f"Security Policy Denial: {decision.reason}",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )

        if decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION:
            return ToolExecutionResult(
                success=False,
                output={
                    "status": "CONFIRMATION_REQUIRED",
                    "tool": tool_name,
                    "arguments": arguments,
                },
                error=f"User confirmation required: {decision.reason}",
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )

        # 3. Execution via OS Adapter
        success = False
        output: Any = None
        error: str | None = None

        try:
            output = await self._dispatch_to_adapter(tool_name, arguments)
            success = True
        except Exception as err:
            logger.error("Error executing OS adapter capability '%s': %s", tool_name, err)
            error = str(err)
            success = False

        duration_ms = int((time.perf_counter() - t0) * 1000)

        # 4. Audit Trail Logging
        PolicyEngine.create_audit_record(
            actor_id=session_id,
            tool_spec=tool_spec,
            arguments=arguments,
            decision=decision,
            trace_id=trace_id,
            execution_success=success,
        )

        result = ToolExecutionResult(
            success=success,
            output=output,
            error=error,
            duration_ms=duration_ms,
            evidence={"tool_name": tool_name, "arguments": arguments},
        )

        # Cache for idempotency if write operation
        if tool_spec.risk_class != RiskClass.READ and success:
            idem_key = self._compute_idempotency_key(tool_name, arguments, session_id)
            self._idempotency_cache[idem_key] = result

        return result

    def _resolve_tool_and_args(self, packet: IntentPacket) -> tuple[str | None, dict[str, Any]]:
        """Maps IntentPacket to specific tool name and argument dictionary."""
        target = packet.target_intent
        entities = packet.extracted_entities

        if target == "TIMER":
            action = entities.get("action", TimerAction.SET)
            if action == TimerAction.SET:
                return "set_timer", {
                    "duration_seconds": entities.get("duration_seconds", 0),
                    "label": entities.get("label", "Timer"),
                }
            elif action == TimerAction.CANCEL:
                return "cancel_timer", {"timer_id": entities.get("timer_id")}
            elif action == TimerAction.STATUS:
                return "get_timer_status", {"timer_id": entities.get("timer_id")}

        elif target == "ALARM":
            action = entities.get("action", AlarmAction.SET)
            if action == AlarmAction.SET:
                target_time = entities.get("target_time")
                if isinstance(target_time, str):
                    target_time = datetime.fromisoformat(target_time)
                elif target_time is None:
                    target_time = datetime.now()
                return "set_alarm", {
                    "target_time": target_time,
                    "label": entities.get("label", "Alarm"),
                    "repeat": entities.get("repeat"),
                }
            elif action == AlarmAction.CANCEL:
                return "cancel_alarm", {"alarm_id": entities.get("alarm_id")}
            elif action == AlarmAction.LIST:
                return "list_alarms", {}

        elif target == "REMINDER":
            action = entities.get("action", ReminderAction.SET)
            if action == ReminderAction.SET:
                target_time = entities.get("target_time")
                if isinstance(target_time, str):
                    target_time = datetime.fromisoformat(target_time)
                elif target_time is None:
                    target_time = datetime.now()
                return "set_reminder", {
                    "text": entities.get("text", "Reminder"),
                    "target_time": target_time,
                }
            elif action == ReminderAction.LIST:
                return "list_reminders", {}
            elif action == ReminderAction.CANCEL:
                return "cancel_reminder", {"reminder_id": entities.get("reminder_id")}

        elif target == "VOLUME":
            action = entities.get("action")
            if action == VolumeAction.SET:
                return "set_volume", {"level": entities.get("level", 50)}
            elif action == VolumeAction.INCREASE:
                return "adjust_volume", {"delta": entities.get("step", 10)}
            elif action == VolumeAction.DECREASE:
                return "adjust_volume", {"delta": -entities.get("step", 10)}
            elif action == VolumeAction.MUTE:
                return "mute_volume", {}
            elif action == VolumeAction.UNMUTE:
                return "unmute_volume", {}

        elif target == "APP_LAUNCH":
            action = entities.get("action", AppAction.OPEN)
            app_name = entities.get("app_name", "")
            if action == AppAction.OPEN:
                return "launch_app", {"app_name": app_name}
            elif action == AppAction.CLOSE:
                return "close_app", {"app_name": app_name}

        elif target == "SYSTEM_QUERY":
            q_type = entities.get("query_type")
            if q_type in [SystemQueryType.TIME, SystemQueryType.DATE]:
                return "get_system_time", {}
            elif q_type == SystemQueryType.BATTERY:
                return "get_battery_status", {}
            elif q_type == SystemQueryType.STATUS:
                return "get_battery_status", {}

        return None, {}

    async def _dispatch_to_adapter(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Invokes the specific OS adapter method."""
        if tool_name == "set_timer":
            return await self.os_adapter.set_timer(
                args["duration_seconds"], args.get("label", "Timer")
            )
        elif tool_name == "cancel_timer":
            return await self.os_adapter.cancel_timer(args.get("timer_id"))
        elif tool_name == "get_timer_status":
            return await self.os_adapter.get_timer_status(args.get("timer_id"))
        elif tool_name == "set_alarm":
            return await self.os_adapter.set_alarm(
                args["target_time"], args.get("label", "Alarm"), args.get("repeat")
            )
        elif tool_name == "cancel_alarm":
            return await self.os_adapter.cancel_alarm(args.get("alarm_id"))
        elif tool_name == "list_alarms":
            return await self.os_adapter.list_alarms()
        elif tool_name == "set_reminder":
            return await self.os_adapter.set_reminder(args["text"], args["target_time"])
        elif tool_name == "list_reminders":
            return await self.os_adapter.list_reminders()
        elif tool_name == "cancel_reminder":
            return await self.os_adapter.cancel_reminder(args.get("reminder_id"))
        elif tool_name == "set_volume":
            return await self.os_adapter.set_volume(args["level"])
        elif tool_name == "adjust_volume":
            return await self.os_adapter.adjust_volume(args["delta"])
        elif tool_name == "mute_volume":
            return await self.os_adapter.mute_volume()
        elif tool_name == "unmute_volume":
            return await self.os_adapter.unmute_volume()
        elif tool_name == "launch_app":
            return await self.os_adapter.launch_app(args["app_name"])
        elif tool_name == "close_app":
            return await self.os_adapter.close_app(args["app_name"])
        elif tool_name == "get_system_time":
            return await self.os_adapter.get_system_time()
        elif tool_name == "get_battery_status":
            return await self.os_adapter.get_battery_status()
        raise ValueError(f"Unknown tool name: {tool_name}")
