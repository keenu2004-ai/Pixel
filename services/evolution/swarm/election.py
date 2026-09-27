"""PIXEL — Dynamic Leader Election & Swarm Lease Management.

Provides deterministic leader election, lease expiration, heartbeat validation,
and split-brain prevention for collaborative multi-agent swarms.
"""

from datetime import UTC, datetime, timedelta

from packages.contracts.evolution import SwarmAgentIdentity, SwarmLease


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


class LeaderElection:
    """Manages epoch-based leader leases and failover for a swarm session."""

    def __init__(self, swarm_id: str, lease_duration_seconds: float = 30.0) -> None:
        self.swarm_id = swarm_id
        self.lease_duration = timedelta(seconds=lease_duration_seconds)
        self.current_epoch: int = 1
        self.current_leader_id: str | None = None
        self.current_lease: SwarmLease | None = None
        self._heartbeats: dict[str, datetime] = {}

    def record_heartbeat(self, agent_id: str) -> None:
        """Records a timestamped heartbeat for an agent."""
        self._heartbeats[agent_id] = _utc_now()

    def is_leader_alive(self) -> bool:
        """Checks if current leader exists, lease is active, and heartbeat is fresh."""
        if not self.current_leader_id or not self.current_lease:
            return False

        if not self.current_lease.is_active:
            return False

        # Check lease expiration
        try:
            expires_at = datetime.fromisoformat(self.current_lease.expires_at)
            if _utc_now() >= expires_at:
                return False
        except Exception:
            return False

        # Check heartbeat freshness (must have heartbeat within lease duration)
        last_hb = self._heartbeats.get(self.current_leader_id)
        if not last_hb:
            return False

        return (_utc_now() - last_hb) <= self.lease_duration

    def elect_leader(self, candidates: dict[str, SwarmAgentIdentity]) -> str | None:
        """Elects a new leader deterministically from available healthy candidates.

        Selection criteria:
        1. Trust level (descending)
        2. Role priority (COORDINATOR > PLANNER > RESEARCHER > others)
        3. Lexicographical agent_id (tie-breaker)
        """
        if not candidates:
            self.current_leader_id = None
            self.current_lease = None
            return None

        role_priority = {
            "COORDINATOR": 100,
            "PLANNER": 80,
            "DIAGNOSTICIAN": 70,
            "RESEARCHER": 60,
            "CODER": 50,
            "TESTER": 50,
            "REVIEWER": 50,
            "MEMORY_REPLICATOR": 40,
            "MODEL_EVALUATOR": 40,
            "MODEL_ENGINEER": 40,
            "OBSERVER": 10,
        }

        # Filter candidates with recent heartbeats
        now = _utc_now()
        alive_candidates = [
            cand
            for cand_id, cand in candidates.items()
            if cand_id in self._heartbeats
            and (now - self._heartbeats[cand_id]) <= self.lease_duration
        ]

        # If no heartbeats recorded yet (e.g. startup), allow all registered candidates
        pool = alive_candidates if alive_candidates else list(candidates.values())

        if not pool:
            return None

        sorted_candidates = sorted(
            pool,
            key=lambda c: (
                c.trust_level,
                role_priority.get(c.role.value, 0),
                c.agent_id,
            ),
            reverse=True,
        )

        new_leader = sorted_candidates[0]
        self.current_epoch += 1
        self.current_leader_id = new_leader.agent_id

        lease_id = f"lease-{self.swarm_id}-ep{self.current_epoch}-{new_leader.agent_id}"
        expires_at = (now + self.lease_duration).isoformat()

        self.current_lease = SwarmLease(
            lease_id=lease_id,
            leader_agent_id=new_leader.agent_id,
            epoch=self.current_epoch,
            granted_at=now.isoformat(),
            expires_at=expires_at,
            is_active=True,
        )

        return self.current_leader_id

    def renew_lease(self, agent_id: str, epoch: int) -> bool:
        """Renews leadership lease if agent is current leader and epoch matches."""
        if agent_id != self.current_leader_id:
            return False

        if epoch != self.current_epoch:
            return False

        now = _utc_now()
        expires_at = (now + self.lease_duration).isoformat()
        if self.current_lease:
            self.current_lease.expires_at = expires_at
            self.current_lease.is_active = True
        self.record_heartbeat(agent_id)
        return True

    def revoke_leadership(self, reason: str = "administrative") -> None:
        """Revokes the current leadership lease immediately."""
        if self.current_lease:
            self.current_lease.is_active = False
        self.current_leader_id = None
