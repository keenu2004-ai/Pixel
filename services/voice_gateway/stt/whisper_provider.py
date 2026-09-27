"""Local Whisper Speech-to-Text Provider (Faster-Whisper / ONNX).

Provides lazy-loaded, memory-bounded, multilingual speech transcription.
"""

import io
import logging
import wave
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import numpy as np

from packages.contracts.errors import ModelException, ProviderUnavailableException
from packages.contracts.events import AudioFrame, TranscriptEvent
from packages.core.interfaces.stt import BaseSTTProvider

logger = logging.getLogger(__name__)


def _pcm_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Converts 16-bit PCM mono bytes to float32 numpy array normalized to [-1.0, 1.0]."""
    if not pcm_bytes:
        return np.array([], dtype=np.float32)
    audio_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
    return (audio_int16.astype(np.float32) / 32768.0).copy()


def _pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wraps raw PCM bytes in a standard WAV container header."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return wav_io.getvalue()


class LocalWhisperSTT(BaseSTTProvider):
    """Local Faster-Whisper / CT2 speech-to-text engine with lazy initialization."""

    def __init__(
        self,
        model_size_or_path: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        beam_size: int = 5,
        default_language: str | None = None,
    ) -> None:
        self.model_size_or_path = model_size_or_path
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.beam_size = beam_size
        self.default_language = default_language
        self._model: Any = None
        self._is_loaded = False

    def is_available(self) -> bool:
        """Checks if faster-whisper dependency is available and model path exists if local."""
        try:
            import faster_whisper  # noqa: F401

            if (
                self.model_size_or_path.endswith((".bin", ".pt", ".onnx"))
                or "/" in self.model_size_or_path
                or "\\" in self.model_size_or_path
            ):
                path = Path(self.model_size_or_path)
                return path.exists()
            return True
        except ImportError:
            return False

    def _ensure_loaded(self) -> Any:
        """Lazy loads Faster-Whisper model on first inference request."""
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as err:
            raise ProviderUnavailableException(
                "faster-whisper is not installed. Install with 'pip install faster-whisper' or use CloudSTTProvider."
            ) from err

        try:
            logger.info(
                "Loading Faster-Whisper model: %s (device=%s, compute=%s)",
                self.model_size_or_path,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                model_size_or_path=self.model_size_or_path,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
            self._is_loaded = True
            return self._model
        except Exception as err:
            raise ModelException(f"Failed to load Faster-Whisper model: {err}") from err

    def _normalize_language(self, language: str | None) -> str | None:
        """Normalizes language codes (e.g., Hinglish/hi-Latn to hi/en)."""
        if not language or language.lower() in ("auto", "none"):
            return None
        lang = language.lower().strip()
        if lang in ("hinglish", "hi-latn", "hi_in"):
            return "hi"
        if lang.startswith("en"):
            return "en"
        if lang.startswith("hi"):
            return "hi"
        return lang

    async def transcribe_once(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> TranscriptEvent:
        """Transcribes a discrete PCM audio byte buffer into a TranscriptEvent."""
        if not audio_bytes:
            return TranscriptEvent(
                session_id="default",
                text="",
                is_final=True,
                confidence=1.0,
                language=language or self.default_language or "en",
                provider="local_whisper",
            )

        model = self._ensure_loaded()
        audio_float = _pcm_to_float32(audio_bytes)
        if len(audio_float) == 0:
            return TranscriptEvent(
                session_id="default",
                text="",
                is_final=True,
                confidence=1.0,
                language=language or self.default_language or "en",
                provider="local_whisper",
            )

        target_lang = self._normalize_language(language or self.default_language)

        try:
            segments, info = model.transcribe(
                audio_float,
                beam_size=self.beam_size,
                language=target_lang,
                vad_filter=False,
            )
            text_parts = [s.text.strip() for s in segments]
            full_text = " ".join(text_parts).strip()
            detected_lang = getattr(info, "language", target_lang or "en")
            prob = getattr(info, "language_probability", 1.0)
            duration = int(getattr(info, "duration", len(audio_float) / 16000.0) * 1000)

            return TranscriptEvent(
                session_id="default",
                text=full_text,
                is_final=True,
                confidence=float(prob),
                language=detected_lang,
                duration_ms=duration,
                provider="local_whisper",
                metadata={"all_languages": getattr(info, "all_language_probs", None)},
            )
        except Exception as err:
            logger.error("Local Whisper transcription error: %s", err)
            raise ModelException(f"Whisper inference error: {err}") from err

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        session_id: str,
        language: str | None = None,
    ) -> AsyncIterator[TranscriptEvent]:
        """Consumes an async stream of AudioFrames and yields interim and final transcripts."""
        buffer = bytearray()
        chunk_interval_bytes = 16000 * 2 * 1  # 1 second of 16kHz 16-bit mono
        target_lang = self._normalize_language(language or self.default_language)

        async for frame in audio_stream:
            buffer.extend(frame.pcm_data)
            # Emit interim hypothesis every ~1 second of accumulated audio
            if len(buffer) >= chunk_interval_bytes and len(buffer) % (16000 * 2 // 2) == 0:
                try:
                    interim_res = await self.transcribe_once(bytes(buffer), language=target_lang)
                    if interim_res.text:
                        yield TranscriptEvent(
                            session_id=session_id,
                            text=interim_res.text,
                            is_final=False,
                            confidence=interim_res.confidence,
                            language=interim_res.language,
                            provider="local_whisper",
                        )
                except Exception as err:
                    logger.debug("Interim stream transcription skipped on frame: %s", err)

        # Final pass when stream closes
        if buffer:
            final_res = await self.transcribe_once(bytes(buffer), language=target_lang)
            yield TranscriptEvent(
                session_id=session_id,
                text=final_res.text,
                is_final=True,
                confidence=final_res.confidence,
                language=final_res.language,
                duration_ms=final_res.duration_ms,
                provider="local_whisper",
                metadata=final_res.metadata,
            )
