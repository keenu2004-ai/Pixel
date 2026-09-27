"""Unit tests for VoiceSession state machine and cancellation."""

import asyncio

import pytest

from packages.contracts.events import VoiceState
from services.voice_gateway.session import VoiceSession


def test_session_initial_state() -> None:
    session = VoiceSession(session_id="test_001")
    assert session.session_id == "test_001"
    assert session.state == VoiceState.IDLE
    assert not session.is_playback_cancelled


def test_session_state_transition() -> None:
    session = VoiceSession(session_id="test_002")
    event = session.transition_to(VoiceState.LISTENING, reason="User triggered wake word")

    assert session.state == VoiceState.LISTENING
    assert event.previous_state == VoiceState.IDLE
    assert event.current_state == VoiceState.LISTENING
    assert event.reason == "User triggered wake word"
    assert session.state_history == [VoiceState.IDLE, VoiceState.LISTENING]


def test_session_playback_cancellation() -> None:
    session = VoiceSession(session_id="test_003")
    assert not session.is_playback_cancelled

    session.cancel_active_playback()
    assert session.is_playback_cancelled

    session.reset_cancellation()
    assert not session.is_playback_cancelled


@pytest.mark.asyncio
async def test_session_active_tts_task_cancellation() -> None:
    session = VoiceSession(session_id="test_004")

    async def dummy_coro() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(dummy_coro())
    session.set_active_tts_task(task)

    cancelled = session.cancel_active_playback()
    assert cancelled is True
    assert task.cancelling() > 0 or task.cancelled()
    await asyncio.sleep(0.01)
    assert task.cancelled() or task.done()
