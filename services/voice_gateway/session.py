"""Voice Session State Manager.

Maintains active session context, state machine transitions, and thread-safe cancellation tokens.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from packages.contracts.events import StateChangeEvent, VoiceState
from services.voice_gateway.audio.stream_buffer import AudioStreamBuffer

logger = logging.getLogger(__name__)


class VoiceSession:
    """Represents a live active voice interaction session with a client."""

    def __init__(
        self,
        session_id: str,
        max_frames: int = 1000,
        max_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.session_id = session_id
        self.state: VoiceState = VoiceState.IDLE
        self.buffer = AudioStreamBuffer(max_frames=max_frames, max_bytes=max_bytes)
        self.created_at = datetime.now(UTC)
        self.last_active_at = datetime.now(UTC)
        self._current_tts_task: asyncio.Task[Any] | None = None
        self._playback_cancel_event = asyncio.Event()
        self.state_history: list[VoiceState] = [VoiceState.IDLE]

    def transition_to(self, new_state: VoiceState, reason: str = "") -> StateChangeEvent:
        """Transitions to a new VoiceState and records history."""
        old_state = self.state
        self.state = new_state
        self.last_active_at = datetime.now(UTC)
        self.state_history.append(new_state)
        logger.info(
            "Session [%s] state transition: %s -> %s (reason: %s)",
            self.session_id,
            old_state.value,
            new_state.value,
            reason or "none",
        )
        return StateChangeEvent(
            session_id=self.session_id,
            previous_state=old_state,
            current_state=new_state,
            reason=reason,
        )

    def cancel_active_playback(self) -> bool:
        """Cancels any ongoing TTS generation or audio playback immediately."""
        self._playback_cancel_event.set()
        if self._current_tts_task and not self._current_tts_task.done():
            self._current_tts_task.cancel()
            self._current_tts_task = None
            logger.info("Session [%s] active TTS task cancelled.", self.session_id)
            return True
        return False

    def reset_cancellation(self) -> None:
        """Resets the playback cancellation token."""
        self._playback_cancel_event.clear()

    @property
    def is_playback_cancelled(self) -> bool:
        """Returns True if playback cancellation was requested."""
        return self._playback_cancel_event.is_set()

    def set_active_tts_task(self, task: asyncio.Task[Any]) -> None:
        """Registers the currently executing TTS streaming task."""
        self._current_tts_task = task
