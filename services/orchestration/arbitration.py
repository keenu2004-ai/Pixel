"""Multi-Satellite Audio Coordination & Wake-Event Arbiter.

Performs sliding-window deduplication, multi-signal candidate scoring,
active-device election, and audio ownership management to prevent duplicate
utterance execution across multiple room microphones/satellites.
"""

import threading
from datetime import UTC, datetime
from uuid import uuid4

from packages.contracts.orchestration import (
    WakeArbitrationCandidate,
    WakeArbitrationResult,
)


class WakeArbiter:
    """Central arbiter for multi-device wake events and audio capture ownership."""

    def __init__(self, dedup_window_ms: int = 1500) -> None:
        self.dedup_window_ms = dedup_window_ms
        self._lock = threading.RLock()
        self._active_audio_owner: str | None = None
        # Maps wake_event_id -> list[WakeArbitrationCandidate]
        self._event_groups: dict[str, list[WakeArbitrationCandidate]] = {}
        # Maps wake_event_id -> active audio owner at time of event creation
        self._event_prior_owner: dict[str, str | None] = {}
        # Maps wake_event_id -> WakeArbitrationResult
        self._settled_events: dict[str, WakeArbitrationResult] = {}
        # Timestamps of recent events for sliding window cleanup
        self._event_timestamps: dict[str, int] = {}


    def calculate_score(
        self,
        candidate: WakeArbitrationCandidate,
        interaction_owner: str | None = None,
        enforce_owner: bool = False,
    ) -> float:
        """Calculate deterministic composite score for a wake candidate."""
        score = 0.0

        # Confidence component (0.0 to 1.0 -> 0 to 50 pts)
        score += candidate.confidence * 50.0

        # Signal-to-Noise Ratio (dB) component
        score += candidate.snr_db * 1.0

        # Estimated distance penalty (-10 pts per meter)
        if candidate.estimated_distance_m is not None:
            score -= candidate.estimated_distance_m * 10.0

        # Round trip latency penalty (-0.1 pt per ms)
        score -= candidate.rtt_ms * 0.1

        # Active interaction owner boost (+100 pts)
        owner = interaction_owner if enforce_owner else (interaction_owner or self._active_audio_owner)
        if candidate.is_current_interaction_owner or (owner is not None and owner == candidate.device_id):
            score += 100.0

        return score

    def register_candidate(
        self,
        candidate: WakeArbitrationCandidate,
    ) -> WakeArbitrationResult:
        """Ingest a wake candidate frame and evaluate arbitration across all candidates."""
        with self._lock:
            event_id = candidate.wake_event_id

            if event_id not in self._event_groups:
                self._event_groups[event_id] = []
                self._event_timestamps[event_id] = candidate.timestamp_ms
                self._event_prior_owner[event_id] = self._active_audio_owner

            prior_owner = self._event_prior_owner.get(event_id)

            # Deduplicate repeated transmissions from same device for same event
            existing_dev_cand = next(
                (c for c in self._event_groups[event_id] if c.device_id == candidate.device_id),
                None,
            )
            if existing_dev_cand is None:
                self._event_groups[event_id].append(candidate)

            candidates = self._event_groups[event_id]

            # Score all candidates in group with consistent baseline owner
            scored = [(c, self.calculate_score(c, interaction_owner=prior_owner, enforce_owner=True)) for c in candidates]
            # Deterministic sorting: highest score first, then lowest timestamp_ms, then device_id
            scored.sort(key=lambda item: (-item[1], item[0].timestamp_ms, item[0].device_id))


            winner_candidate, winner_score = scored[0]
            suppressed = [c.device_id for c, _ in scored if c.device_id != winner_candidate.device_id]

            result = WakeArbitrationResult(
                arbitration_id=uuid4().hex,
                wake_event_id=event_id,
                winner_device_id=winner_candidate.device_id,
                winner_score=winner_score,
                suppressed_device_ids=suppressed,
                candidates_evaluated=len(candidates),
                timestamp=datetime.now(UTC),
            )

            # Update settled record and audio owner
            self._settled_events[event_id] = result
            self._active_audio_owner = winner_candidate.device_id
            return result



    def get_active_audio_owner(self) -> str | None:
        """Get currently active audio owner device ID."""
        with self._lock:
            return self._active_audio_owner

    def set_active_audio_owner(self, device_id: str) -> None:
        """Explicitly set current active audio owner device."""
        with self._lock:
            self._active_audio_owner = device_id

    def release_audio_owner(self, device_id: str | None = None) -> None:
        """Release audio ownership if held by specified device or universally."""
        with self._lock:
            if device_id is None or self._active_audio_owner == device_id:
                self._active_audio_owner = None
