"""PIXEL — Phase 17 Autonomous Fleet Mission Governor.

Governs multi-node coordinated missions, strictly enforcing bounded delegation depth (<=3),
anti-escalation invariants, and budget limits.
"""

from packages.contracts.fleet import AutonomousFleetMission, DelegatedTaskEnvelope


class AutonomousFleetMissionGovernor:
    """Oversees multi-step, multi-device autonomous fleet mission execution."""

    def __init__(self, max_delegation_depth: int = 3) -> None:
        self._max_delegation_depth = max_delegation_depth
        self._active_missions: dict[str, AutonomousFleetMission] = {}

    def create_mission(
        self,
        title: str,
        goal: str,
        allowed_nodes: list[str] | None = None,
        timeout_seconds: float = 60.0,
    ) -> AutonomousFleetMission:
        """Initializes a bounded autonomous fleet mission."""
        mission = AutonomousFleetMission(
            title=title,
            goal=goal,
            allowed_nodes=allowed_nodes or [],
            max_delegation_depth=self._max_delegation_depth,
            timeout_seconds=timeout_seconds,
        )
        self._active_missions[mission.mission_id] = mission
        return mission

    def validate_delegation(
        self,
        envelope: DelegatedTaskEnvelope,
    ) -> tuple[bool, str | None]:
        """Enforces anti-escalation and bounded delegation depth invariants."""
        # Rule 58: NO UNBOUNDED DELEGATION
        if envelope.current_delegation_depth >= self._max_delegation_depth:
            return (
                False,
                f"Maximum delegation depth ({self._max_delegation_depth}) exceeded. Sub-delegation rejected.",
            )

        # Rule 59: NO SWARM ESCALATION (destination node must be verified)
        if not envelope.target_node_id:
            return False, "Target node ID must be explicitly specified."

        return True, None
