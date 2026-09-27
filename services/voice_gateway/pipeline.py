"""Voice Pipeline Orchestrator.

Integrates AudioStreamBuffer, VAD, Wake Word, STT, Deterministic Intent Engine,
and TTS with zero-latency barge-in interruption and state transitions.
"""

import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from packages.contracts.events import (
    AudioFrame,
    BaseEvent,
    VADState,
    VoiceState,
)
from packages.core.interfaces.stt import BaseSTTProvider
from packages.core.interfaces.tts import BaseTTSProvider
from packages.core.interfaces.vad import BaseVADProvider
from packages.core.interfaces.wake import BaseWakeProvider
from services.intent_engine.engine import DeterministicIntentEngine
from services.voice_gateway.session import VoiceSession

logger = logging.getLogger(__name__)


class VoicePipeline:
    """Orchestrates end-to-end voice perception, intent triggering, synthesis, and barge-in."""

    def __init__(
        self,
        vad_provider: BaseVADProvider,
        wake_provider: BaseWakeProvider,
        stt_provider: BaseSTTProvider,
        tts_provider: BaseTTSProvider,
        intent_engine: DeterministicIntentEngine | None = None,
        intent_handler: Callable[[str, str], Any] | None = None,
    ) -> None:
        self.vad_provider = vad_provider
        self.wake_provider = wake_provider
        self.stt_provider = stt_provider
        self.tts_provider = tts_provider
        self.intent_engine = intent_engine or DeterministicIntentEngine()
        self.intent_handler = intent_handler
        self._speech_buffer = bytearray()

    async def _resolve_intent_response(self, text: str, session_id: str) -> str:
        """Executes intent through DeterministicIntentEngine or custom intent handler."""
        if self.intent_handler is not None:
            res = await self.intent_handler(text, session_id)
            return str(res)

        response_text, _, _ = await self.intent_engine.handle_transcript(text, session_id=session_id)
        return response_text

    async def process_frame(
        self,
        frame: AudioFrame,
        session: VoiceSession,
    ) -> AsyncIterator[BaseEvent | bytes]:
        """Processes an incoming PCM AudioFrame through VAD, Wake Word, and STT pipelines."""
        # 1. Run VAD
        vad_event = await self.vad_provider.process_frame(frame, session_id=session.session_id)

        # 2. Check for Barge-in Interruption
        if session.state == VoiceState.SPEAKING:
            if vad_event.state == VADState.SPEECH_START or vad_event.speech_probability > 0.8:
                logger.info("Barge-in detected during SPEAKING state in session [%s]", session.session_id)
                session.cancel_active_playback()
                interrupted_evt = session.transition_to(
                    VoiceState.INTERRUPTED, reason="User barged in / started speaking"
                )
                yield interrupted_evt
                listening_evt = session.transition_to(
                    VoiceState.LISTENING, reason="Transitioned from barge-in to active listening"
                )
                yield listening_evt
                self._speech_buffer.clear()
                self._speech_buffer.extend(frame.pcm_data)
                return

        # 3. If IDLE, listen for wake word
        if session.state == VoiceState.IDLE:
            wake_event = await self.wake_provider.process_frame(frame, session_id=session.session_id)
            if wake_event is not None:
                yield wake_event
                listening_evt = session.transition_to(
                    VoiceState.LISTENING, reason=f"Wake phrase triggered: {wake_event.phrase}"
                )
                yield listening_evt
                self._speech_buffer.clear()
            return

        # 4. If LISTENING, accumulate speech frames and check for speech end
        if session.state == VoiceState.LISTENING:
            self._speech_buffer.extend(frame.pcm_data)

            # Check if user stopped speaking
            if vad_event.state == VADState.SPEECH_END or (
                vad_event.state == VADState.SILENCE and len(self._speech_buffer) >= 16000 * 2 * 1.0
            ):
                thinking_evt = session.transition_to(VoiceState.THINKING, reason="Speech ended, transcribing")
                yield thinking_evt

                # Transcribe accumulated speech
                captured_audio = bytes(self._speech_buffer)
                self._speech_buffer.clear()

                transcript = await self.stt_provider.transcribe_once(captured_audio)
                transcript.session_id = session.session_id
                yield transcript

                if transcript.text.strip():
                    # Handle intent via real DeterministicIntentEngine
                    response_text = await self._resolve_intent_response(transcript.text, session.session_id)

                    # Transition to SPEAKING and synthesize TTS
                    speaking_evt = session.transition_to(
                        VoiceState.SPEAKING, reason="Starting response speech synthesis"
                    )
                    yield speaking_evt

                    session.reset_cancellation()
                    async for audio_chunk in self.tts_provider.synthesize_stream(response_text):
                        if session.is_playback_cancelled:
                            logger.info("TTS streaming cancelled mid-stream due to barge-in.")
                            break
                        yield audio_chunk

                    # If not interrupted, transition back to IDLE
                    if not session.is_playback_cancelled:
                        idle_evt = session.transition_to(
                            VoiceState.IDLE, reason="Speech playback finished successfully"
                        )
                        yield idle_evt
                else:
                    idle_evt = session.transition_to(VoiceState.IDLE, reason="No speech detected in audio")
                    yield idle_evt
