"""Neural Wake Phrase Detection Provider using ONNX Runtime.

Implements BaseWakeProvider for real-time acoustic wake phrase perception ("Hey Pixel", "Oye Pixel", etc.).
"""

import hashlib
import logging
import os
import time
from typing import Any

import numpy as np

from packages.contracts.errors import ErrorCategory, PixelException
from packages.contracts.events import AudioFrame, WakeEvent
from packages.core.interfaces.wake import BaseWakeProvider

logger = logging.getLogger("pixel.voice.wake_word")


class WakeWordModelIntegrityError(PixelException):
    """Raised when wake word model files fail integrity verification or checksum checks."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.PROVIDER_ERROR,
            code="WAKE_MODEL_INTEGRITY_FAILURE",
        )


class OpenWakeWordConfig:
    """Configuration hyperparameters for the OpenWakeWord ONNX provider."""

    def __init__(
        self,
        model_paths: dict[str, str] | None = None,
        expected_sha256: dict[str, str] | None = None,
        threshold: float = 0.5,
        cooldown_seconds: float = 1.5,
        sample_rate: int = 16000,
        chunk_samples: int = 1280,  # 80ms chunks @ 16kHz
    ) -> None:
        self.model_paths = model_paths or {
            "hey_pixel": "data/models/hey_pixel.onnx",
            "oye_pixel": "data/models/oye_pixel.onnx",
        }
        self.expected_sha256 = expected_sha256 or {}
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples


class _WakeSessionState:
    """Tracks sliding audio window and cooldown state for a specific session."""

    def __init__(self) -> None:
        self.buffer = np.zeros(0, dtype=np.float32)
        self.last_trigger_time: float = 0.0

    def reset(self) -> None:
        self.buffer = np.zeros(0, dtype=np.float32)
        self.last_trigger_time = 0.0


class OpenWakeWordProvider(BaseWakeProvider):
    """Production ONNX-backed multi-phrase Wake Word Provider."""

    def __init__(self, config: OpenWakeWordConfig | None = None) -> None:
        self.config = config or OpenWakeWordConfig()
        self._sessions: dict[str, Any] = {}
        self._session_states: dict[str, _WakeSessionState] = {}
        self._initialized: bool = False
        self._initialization_error: str | None = None

    def get_supported_phrases(self) -> list[str]:
        """Returns list of registered trigger phrases."""
        return list(self.config.model_paths.keys())

    def is_available(self) -> bool:
        """Checks if onnxruntime is installed and at least one model file exists."""
        if not any(os.path.exists(p) for p in self.config.model_paths.values()):
            return False
        try:
            import onnxruntime  # noqa: F401

            return True
        except ImportError:
            return False

    def validate_model_integrity(self) -> None:
        """Validates existence and checksum of all configured model files."""
        for phrase, path in self.config.model_paths.items():
            if not os.path.exists(path):
                raise WakeWordModelIntegrityError(
                    f"Wake word model for '{phrase}' not found at '{path}'."
                )
            if phrase in self.config.expected_sha256:
                expected = self.config.expected_sha256[phrase]
                sha256 = hashlib.sha256()
                with open(path, "rb") as f:
                    while chunk := f.read(65536):
                        sha256.update(chunk)
                actual = sha256.hexdigest().lower()
                if actual != expected.lower():
                    raise WakeWordModelIntegrityError(
                        f"Checksum mismatch for '{phrase}' model at '{path}'. Expected {expected}, got {actual}."
                    )

    def initialize(self) -> None:
        """Lazily loads ONNX runtime inference sessions for all wake models."""
        if self._initialized:
            return

        self.validate_model_integrity()

        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            for phrase, path in self.config.model_paths.items():
                session = ort.InferenceSession(
                    path, sess_options=opts, providers=["CPUExecutionProvider"]
                )
                self._sessions[phrase] = session

            self._initialized = True
            logger.info(f"OpenWakeWord sessions initialized for {list(self._sessions.keys())}.")
        except ImportError as err:
            self._initialization_error = "onnxruntime not installed"
            raise PixelException(
                message="onnxruntime is required for OpenWakeWordProvider.",
                category=ErrorCategory.PROVIDER_ERROR,
                code="ONNXRUNTIME_MISSING",
            ) from err
        except Exception as err:
            self._initialization_error = str(err)
            raise PixelException(
                message=f"Failed to load OpenWakeWord model sessions: {err}",
                category=ErrorCategory.PROVIDER_ERROR,
                code="WAKE_LOAD_FAILURE",
            ) from err

    def _get_or_create_session_state(self, session_id: str) -> _WakeSessionState:
        if session_id not in self._session_states:
            self._session_states[session_id] = _WakeSessionState()
        return self._session_states[session_id]

    async def shutdown(self) -> None:
        """Releases all model sessions and session buffers."""
        self._sessions.clear()
        self._session_states.clear()
        self._initialized = False
        logger.info("OpenWakeWord provider shut down.")

    async def process_frame(self, frame: AudioFrame, session_id: str) -> WakeEvent | None:
        """Processes an AudioFrame. Returns WakeEvent if a wake phrase reaches detection threshold."""
        if not self._initialized:
            if not self.is_available():
                return None
            self.initialize()

        if not self._sessions:
            return None

        sess_state = self._get_or_create_session_state(session_id)
        now = time.time()

        # Check cooldown period to prevent multiple rapid triggers
        if (now - sess_state.last_trigger_time) < self.config.cooldown_seconds:
            return None

        # 1. Convert incoming PCM int16 to float32 (-1.0 to 1.0)
        audio_int16 = np.frombuffer(frame.pcm_data, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        # 2. Append to rolling session audio buffer
        sess_state.buffer = np.concatenate([sess_state.buffer, audio_float32])

        # Buffer ceiling safety (keep max 3 seconds of rolling audio @ 16kHz = 48000 samples)
        max_buffer_samples = self.config.sample_rate * 3
        if len(sess_state.buffer) > max_buffer_samples:
            sess_state.buffer = sess_state.buffer[-max_buffer_samples:]

        # If buffer doesn't have minimum chunk size, wait for more frames
        if len(sess_state.buffer) < self.config.chunk_samples:
            return None

        # 3. Evaluate each loaded wake model
        best_phrase: str | None = None
        best_score: float = 0.0

        # Prepare input slice
        window_input = sess_state.buffer[-self.config.chunk_samples :]
        input_tensor = np.expand_dims(window_input, axis=0)  # Shape (1, N)

        for phrase, session in self._sessions.items():
            input_name = session.get_inputs()[0].name
            ort_inputs = {input_name: input_tensor}
            ort_outputs = session.run(None, ort_inputs)
            score = float(np.array(ort_outputs[0]).flatten()[0])

            if score > best_score:
                best_score = score
                best_phrase = phrase

        # 4. Check against activation threshold
        if best_phrase and best_score >= self.config.threshold:
            sess_state.last_trigger_time = now
            sess_state.buffer = np.zeros(0, dtype=np.float32)  # Flush buffer after trigger
            readable_phrase = best_phrase.replace("_", " ").title()

            logger.info(f"Wake word detected: '{readable_phrase}' (confidence: {best_score:.3f})")
            return WakeEvent(
                session_id=session_id,
                phrase=readable_phrase,
                confidence=best_score,
                offset_ms=frame.timestamp_ms,
            )

        return None
