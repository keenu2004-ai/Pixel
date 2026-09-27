"""PIXEL — Continuous Runtime Self-Profiler.

Observation-first telemetry collector measuring latency, queue depth, tool execution durations,
error rates, token consumption, and memory sync lag across PIXEL subsystems.
"""

from collections import deque
from datetime import UTC, datetime

from packages.contracts.evolution import SystemProfileMetric


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RuntimeSelfProfiler:
    """Collects and aggregates runtime system metrics in bounded ring buffers."""

    def __init__(self, max_samples_per_metric: int = 1000) -> None:
        self.max_samples = max_samples_per_metric
        self._buffers: dict[str, deque[SystemProfileMetric]] = {}

    def record_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "ms",
        tags: dict[str, str] | None = None,
    ) -> SystemProfileMetric:
        """Records a single telemetry sample into the appropriate ring buffer."""
        metric = SystemProfileMetric(
            metric_name=metric_name,
            timestamp_utc=_utc_now_iso(),
            value=value,
            unit=unit,
            tags=tags or {},
        )
        if metric_name not in self._buffers:
            self._buffers[metric_name] = deque(maxlen=self.max_samples)
        self._buffers[metric_name].append(metric)
        return metric

    def get_metric_samples(self, metric_name: str, limit: int = 100) -> list[SystemProfileMetric]:
        """Retrieves recent samples for a given metric name."""
        buf = self._buffers.get(metric_name)
        if not buf:
            return []
        items = list(buf)
        return items[-limit:]

    def get_summary_stats(self, metric_name: str) -> dict[str, float] | None:
        """Calculates count, min, max, average, and p95 for a metric."""
        buf = self._buffers.get(metric_name)
        if not buf or len(buf) == 0:
            return None

        values = sorted(m.value for m in buf)
        count = len(values)
        p95_idx = int(count * 0.95)
        p95_val = values[min(p95_idx, count - 1)]

        return {
            "count": float(count),
            "min": values[0],
            "max": values[-1],
            "avg": sum(values) / count,
            "p95": p95_val,
        }

    def clear(self) -> None:
        """Clears all in-memory buffers."""
        self._buffers.clear()
