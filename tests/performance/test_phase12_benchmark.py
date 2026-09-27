"""Performance benchmarks and Chaos Failure Injection for Phase 12 Evolution & Swarms."""

import time

from packages.contracts.evolution import (
    AgentProposal,
    AgentVote,
    ReplicatedMemoryItem,
    SwarmAgentIdentity,
    SwarmAgentRole,
    VoteDecision,
)
from services.evolution.memory_mesh.conflict_resolver import MemoryConflictResolver
from services.evolution.models.differential_privacy import DifferentialPrivacyAccountant
from services.evolution.swarm.coordinator import SwarmCoordinator
from services.evolution.swarm.election import LeaderElection


def test_swarm_leader_election_benchmark() -> None:
    election = LeaderElection(swarm_id="bench-swarm")
    candidates = {
        f"agent-{i}": SwarmAgentIdentity(
            agent_id=f"agent-{i}",
            role=SwarmAgentRole.CODER if i > 0 else SwarmAgentRole.COORDINATOR,
            trust_level=0.9 if i > 0 else 1.0,
        )
        for i in range(10)
    }

    start = time.perf_counter()
    for _ in range(100):
        election.elect_leader(candidates)
    duration_ms = (time.perf_counter() - start) * 1000 / 100

    assert duration_ms < 10.0, f"Leader election took {duration_ms:.3f}ms"


def test_consensus_evaluation_benchmark() -> None:
    coordinator = SwarmCoordinator()
    coordinator.create_swarm("bench-swarm-2", "Benchmark Swarm")

    for i in range(5):
        coordinator.register_agent(
            "bench-swarm-2",
            SwarmAgentIdentity(
                agent_id=f"agent-{i}",
                role=SwarmAgentRole.COORDINATOR if i == 0 else SwarmAgentRole.REVIEWER,
                trust_level=1.0,
            ),
        )

    start = time.perf_counter()
    prop = AgentProposal(
        proposal_id="p-bench",
        origin_agent_id="agent-0",
        swarm_id="bench-swarm-2",
        title="Bench Task",
        description="Benchmark task description",
    )
    coordinator.submit_proposal(prop)
    for i in range(5):
        coordinator.vote_on_proposal(
            "bench-swarm-2",
            AgentVote(
                vote_id=f"v-{i}",
                proposal_id="p-bench",
                voter_agent_id=f"agent-{i}",
                voter_role=SwarmAgentRole.COORDINATOR if i == 0 else SwarmAgentRole.REVIEWER,
                decision=VoteDecision.APPROVE,
            ),
        )
    res = coordinator.finalize_proposal("bench-swarm-2", "p-bench")
    duration_ms = (time.perf_counter() - start) * 1000

    assert res.is_approved is True
    assert duration_ms < 25.0, f"Consensus finalization took {duration_ms:.3f}ms"


def test_memory_mesh_conflict_resolution_benchmark() -> None:
    resolver = MemoryConflictResolver()
    item1 = ReplicatedMemoryItem(
        memory_id="mem-bench",
        owner_user_id="user-1",
        version=1,
        vector_clock={"node-1": 1, "node-2": 0},
        origin_node_id="node-1",
        content_payload={"key": "val"},
    )
    item2 = ReplicatedMemoryItem(
        memory_id="mem-bench",
        owner_user_id="user-1",
        version=2,
        vector_clock={"node-1": 1, "node-2": 1},
        origin_node_id="node-2",
        content_payload={"key": "val_updated"},
    )

    start = time.perf_counter()
    for _ in range(500):
        state, item, conf = resolver.resolve(item1, item2)
    duration_ms = (time.perf_counter() - start) * 1000 / 500

    assert duration_ms < 2.0, f"Memory conflict resolution took {duration_ms:.3f}ms"


def test_differential_privacy_noise_benchmark() -> None:
    accountant = DifferentialPrivacyAccountant(epsilon_max=100.0, delta_max=1.0)

    start = time.perf_counter()
    for _ in range(100):
        accountant.add_gaussian_noise(42.0, sensitivity=1.0, epsilon=0.1, delta=1e-5)
    duration_ms = (time.perf_counter() - start) * 1000 / 100

    assert duration_ms < 1.0, f"DP noise generation took {duration_ms:.3f}ms"
