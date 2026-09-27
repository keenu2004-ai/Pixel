"""PIXEL — Differential Privacy Accountant.

Tracks cumulative (epsilon, delta) privacy budgets, calculates noise parameters for Gaussian/Laplace mechanisms,
and prevents private data memorization during personal fine-tuning and model distillation.
"""

import math
import random
from datetime import UTC, datetime

from packages.contracts.evolution import DifferentialPrivacyBudget


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class DifferentialPrivacyAccountant:
    """Manages privacy budget accounting and calibrated noise generation."""

    def __init__(
        self,
        epsilon_max: float = 2.0,
        delta_max: float = 1e-5,
        mechanism: str = "GAUSSIAN",
    ) -> None:
        self.budget = DifferentialPrivacyBudget(
            budget_id="dp-budget-global",
            epsilon_max=epsilon_max,
            epsilon_consumed=0.0,
            delta_max=delta_max,
            delta_consumed=0.0,
            mechanism=mechanism,
            last_updated_at=_utc_now_iso(),
        )

    def can_consume(self, epsilon: float, delta: float = 0.0) -> bool:
        """Checks if the requested privacy budget can be consumed without exceeding maximums."""
        new_eps = self.budget.epsilon_consumed + epsilon
        new_delta = self.budget.delta_consumed + delta
        return new_eps <= self.budget.epsilon_max and new_delta <= self.budget.delta_max

    def consume_budget(self, epsilon: float, delta: float = 0.0) -> bool:
        """Consumes a portion of the privacy budget."""
        if not self.can_consume(epsilon, delta):
            return False

        self.budget.epsilon_consumed += epsilon
        self.budget.delta_consumed += delta
        self.budget.last_updated_at = _utc_now_iso()
        return True

    def add_gaussian_noise(
        self,
        value: float,
        sensitivity: float,
        epsilon: float,
        delta: float,
    ) -> float:
        """Adds calibrated Gaussian noise: sigma = sensitivity * sqrt(2 * ln(1.25 / delta)) / epsilon."""
        if not self.consume_budget(epsilon, delta):
            raise PermissionError("Differential privacy budget exhausted")

        sigma = sensitivity * math.sqrt(2 * math.log(1.25 / delta)) / epsilon
        noise = random.gauss(0, sigma)
        return value + noise

    def add_laplace_noise(
        self,
        value: float,
        sensitivity: float,
        epsilon: float,
    ) -> float:
        """Adds calibrated Laplace noise: scale = sensitivity / epsilon."""
        if not self.consume_budget(epsilon, 0.0):
            raise PermissionError("Differential privacy budget exhausted")

        scale = sensitivity / epsilon
        # Generate Laplace noise from uniform
        u = random.uniform(-0.5, 0.5)
        noise = (
            -scale * math.copysign(1.0, u) * math.log(1.0 - 2.0 * abs(u)) if abs(u) < 0.5 else 0.0
        )
        return value + noise

    def get_remaining_budget(self) -> tuple[float, float]:
        """Returns (remaining_epsilon, remaining_delta)."""
        rem_eps = max(0.0, self.budget.epsilon_max - self.budget.epsilon_consumed)
        rem_delta = max(0.0, self.budget.delta_max - self.budget.delta_consumed)
        return rem_eps, rem_delta
