"""PIXEL — Swarm Agent Failure Detector.

Monitors agent heartbeats, CPU/memory consumption, timeouts, and transitions agent states
between HEALTHY, DEGRADED, UNRESPONSIVE, FAILED, and QUARANTINED.
"""

from datetime import UTC, datetime, timedelta

from packages.contracts.evolution import AgentHeartbeat, SwarmAgentState


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SwarmFailureDetector:
    """Detects stalled, unresponsive, or resource-hogging agents in a swarm."""

    def __init__(
        self,
        heartbeat_timeout_seconds: float = 15.0,
        degraded_latency_seconds: float = 8.0,
        max_cpu_percent: float = 95.0,
        max_memory_mb: float = 2048.0,
    ) -> None:
        self.heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)
        self.degraded_latency = timedelta(seconds=degraded_latency_seconds)
        self.max_cpu_percent = max_cpu_percent
        self.max_memory_mb = max_memory_mb
        self._last_heartbeats: dict[str, AgentHeartbeat] = {}
        self._last_seen: dict[str, datetime] = {}
        self._quarantined_agents: dict[str, str] = {}  # agent_id -> reason

    def record_heartbeat(self, heartbeat: AgentHeartbeat) -> SwarmAgentState:
        """Records an agent heartbeat and evaluates current health status."""
        now = _utc_now()
        agent_id = heartbeat.agent_id

        if agent_id in self._quarantined_agents:
            return SwarmAgentState.QUARANTINED

        self._last_heartbeats[agent_id] = heartbeat
        self._last_seen[agent_id] = now

        # Evaluate resource degradation
        if (
            heartbeat.cpu_usage_percent > self.max_cpu_percent
            or heartbeat.memory_mb > self.max_memory_mb
        ):
            return SwarmAgentState.DEGRADED

        return (
            SwarmAgentState.IDLE if heartbeat.status == SwarmAgentState.IDLE else heartbeat.status
        )

    def evaluate_agent_health(self, agent_id: str) -> SwarmAgentState:
        """Evaluates health status of a specific agent."""
        if agent_id in self._quarantined_agents:
            return SwarmAgentState.QUARANTINED

        last_seen = self._last_seen.get(agent_id)
        if not last_seen:
            return SwarmAgentState.UNRESPONSIVE

        elapsed = _utc_now() - last_seen

        if elapsed > self.heartbeat_timeout:
            return SwarmAgentState.FAILED
        elif elapsed > self.degraded_latency:
            return SwarmAgentState.UNRESPONSIVE

        last_hb = self._last_heartbeats.get(agent_id)
        if last_hb and (
            last_hb.cpu_usage_percent > self.max_cpu_percent
            or last_hb.memory_mb > self.max_memory_mb
        ):
            return SwarmAgentState.DEGRADED

        return last_hb.status if last_hb else SwarmAgentState.IDLE

    def quarantine_agent(self, agent_id: str, reason: str) -> None:
        """Quarantines an agent for malicious or faulty behavior."""
        self._quarantined_agents[agent_id] = reason

    def unquarantine_agent(self, agent_id: str) -> bool:
        """Removes an agent from quarantine."""
        if agent_id in self._quarantined_agents:
            del self._quarantined_agents[agent_id]
            return True
        return False

    def get_unhealthy_agents(self, all_agent_ids: list[str]) -> dict[str, SwarmAgentState]:
        """Returns all agents that are not in IDLE, ASSIGNED, or EXECUTING state."""
        unhealthy: dict[str, SwarmAgentState] = {}
        for aid in all_agent_ids:
            state = self.evaluate_agent_health(aid)
            if state in (
                SwarmAgentState.DEGRADED,
                SwarmAgentState.UNRESPONSIVE,
                SwarmAgentState.FAILED,
                SwarmAgentState.QUARANTINED,
            ):
                unhealthy[aid] = state
        return unhealthy
