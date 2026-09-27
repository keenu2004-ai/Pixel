"""PIXEL — Continuous Autonomous Evolution & Self-Healing Swarms Services."""

from services.evolution.diagnostics.engine import DiagnosticEngine
from services.evolution.diagnostics.profiler import RuntimeSelfProfiler
from services.evolution.governance.governor import EvolutionGovernor
from services.evolution.governance.kill_switches import KillSwitchSystem
from services.evolution.healing.orchestrator import SelfHealingOrchestrator
from services.evolution.healing.proposals import ChangeProposalManager
from services.evolution.healing.regression_generator import RegressionTestGenerator
from services.evolution.memory_mesh.conflict_resolver import MemoryConflictResolver
from services.evolution.memory_mesh.replicator import MemoryMeshReplicator
from services.evolution.models.differential_privacy import DifferentialPrivacyAccountant
from services.evolution.models.distillation import ProgressiveDistillationEngine
from services.evolution.models.evaluator import ModelSafetyEvaluator
from services.evolution.models.lineage import DatasetLineageTracker
from services.evolution.models.registry import EvolutionModelRegistry
from services.evolution.swarm.consensus import HierarchicalConsensusEngine
from services.evolution.swarm.coordinator import SwarmCoordinator
from services.evolution.swarm.election import LeaderElection
from services.evolution.swarm.failure_detector import SwarmFailureDetector

__all__ = [
    "RuntimeSelfProfiler",
    "DiagnosticEngine",
    "KillSwitchSystem",
    "EvolutionGovernor",
    "ChangeProposalManager",
    "RegressionTestGenerator",
    "SelfHealingOrchestrator",
    "MemoryConflictResolver",
    "MemoryMeshReplicator",
    "DifferentialPrivacyAccountant",
    "ProgressiveDistillationEngine",
    "ModelSafetyEvaluator",
    "DatasetLineageTracker",
    "EvolutionModelRegistry",
    "LeaderElection",
    "SwarmFailureDetector",
    "HierarchicalConsensusEngine",
    "SwarmCoordinator",
]
