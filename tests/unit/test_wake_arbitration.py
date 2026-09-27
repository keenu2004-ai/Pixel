"""Unit tests for WakeArbiter and multi-satellite audio coordination."""

import pytest

from packages.contracts.orchestration import (
    WakeArbitrationCandidate,
)
from services.orchestration.arbitration import WakeArbiter


def test_wake_candidate_scoring_logic() -> None:
    arbiter = WakeArbiter()

    cand_close = WakeArbitrationCandidate(
        device_id="sat-close",
        wake_event_id="wake-1",
        timestamp_ms=1000,
        confidence=0.95,
        snr_db=20.0,
        estimated_distance_m=1.0,
        rtt_ms=10.0,
    )
    score_close = arbiter.calculate_score(cand_close)
    # 0.95 * 50 (47.5) + 20.0 - 10.0 - 1.0 = 56.5
    assert score_close == pytest.approx(56.5, 0.1)

    cand_far = WakeArbitrationCandidate(
        device_id="sat-far",
        wake_event_id="wake-1",
        timestamp_ms=1005,
        confidence=0.80,
        snr_db=10.0,
        estimated_distance_m=5.0,
        rtt_ms=30.0,
    )
    score_far = arbiter.calculate_score(cand_far)
    # 0.8 * 50 (40.0) + 10.0 - 50.0 - 3.0 = -3.0
    assert score_far < score_close


def test_multi_satellite_arbitration_and_suppression() -> None:
    arbiter = WakeArbiter()

    # Living room satellite detects wake with high SNR and close proximity
    cand1 = WakeArbitrationCandidate(
        device_id="sat-living-room",
        wake_event_id="utterance-100",
        timestamp_ms=1000,
        confidence=0.98,
        snr_db=25.0,
        estimated_distance_m=1.2,
        rtt_ms=5.0,
    )

    # Kitchen satellite detects wake faintly with lower SNR and farther distance
    cand2 = WakeArbitrationCandidate(
        device_id="sat-kitchen",
        wake_event_id="utterance-100",
        timestamp_ms=1015,
        confidence=0.82,
        snr_db=12.0,
        estimated_distance_m=4.5,
        rtt_ms=15.0,
    )

    res1 = arbiter.register_candidate(cand1)
    res2 = arbiter.register_candidate(cand2)

    assert res1.winner_device_id == "sat-living-room"
    assert res2.winner_device_id == "sat-living-room"
    assert "sat-kitchen" in res2.suppressed_device_ids
    assert arbiter.get_active_audio_owner() == "sat-living-room"


def test_interaction_owner_priority() -> None:
    arbiter = WakeArbiter()
    arbiter.set_active_audio_owner("sat-office")

    # Office satellite detects wake with moderate confidence
    cand_office = WakeArbitrationCandidate(
        device_id="sat-office",
        wake_event_id="utterance-200",
        timestamp_ms=2000,
        confidence=0.85,
        snr_db=15.0,
        is_current_interaction_owner=True,
    )

    # Hallway satellite detects wake with slightly higher raw confidence
    cand_hallway = WakeArbitrationCandidate(
        device_id="sat-hallway",
        wake_event_id="utterance-200",
        timestamp_ms=2000,
        confidence=0.95,
        snr_db=18.0,
    )

    arbiter.register_candidate(cand_hallway)
    res = arbiter.register_candidate(cand_office)

    # Office wins because of active interaction owner boost (+100 pts)
    assert res.winner_device_id == "sat-office"


def test_audio_ownership_lifecycle() -> None:
    arbiter = WakeArbiter()
    assert arbiter.get_active_audio_owner() is None

    arbiter.set_active_audio_owner("sat-01")
    assert arbiter.get_active_audio_owner() == "sat-01"

    # Releasing wrong owner does nothing
    arbiter.release_audio_owner("sat-02")
    assert arbiter.get_active_audio_owner() == "sat-01"

    # Releasing correct owner clears it
    arbiter.release_audio_owner("sat-01")
    assert arbiter.get_active_audio_owner() is None

