"""Silero ONNX Voice Activity Detection (VAD) Provider for PIXEL."""

import hashlib
import logging
import os
from typing import Any

import numpy as np

from packages.contracts.errors import ErrorCategory, PixelException
from packages.contracts.events import AudioFrame, VADEvent, VADState
from packages.core.interfaces.vad import BaseVADProvider

logger = logging.getLogger("pixel.voice.silero_vad")

# Official Silero VAD v5 ONNX SHA-256 digest
SILERO_V5_OFFICIAL_SHA256 = "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"


class SileroModelIntegrityError(PixelException):
    """Raised when Silero model weights fail file verification or checksum."""
    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.PROVIDER_ERROR,
            code="SILERO_MODEL_INTEGRITY_FAILURE"
        )


class SileroVADConfig:
    """Configuration hyperparameters for Silero ONNX VAD."""

    def __init__(
        self,
        model_path: str = "data/models/silero_vad.onnx",
        expected_sha256: str | None = SILERO_V5_OFFICIAL_SHA256,
        threshold: float = 0.5,
        neg_threshold: float = 0.35,
        sample_rate: int = 16000,
        min_speech_duration_ms: int = 64,    # ~2 frames @ 32ms
        min_silence_duration_ms: int = 300,   # ~10 frames @ 32ms
        window_size_samples: int = 512,       # 32ms @ 16kHz
    ) -> None:
        self.model_path = model_path
        self.expected_sha256 = expected_sha256
        self.threshold = threshold
        self.neg_threshold = neg_threshold
        self.sample_rate = sample_rate
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.window_size_samples = window_size_samples


class _SessionState:
    """Tracks recurrent state and temporal smoothing for a specific audio session."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        # Silero VAD v5 recurrent state tensor: shape (2, 1, 128) float32
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.is_speaking: bool = False
        self.speech_frames: int = 0
        self.silence_frames: int = 0

    def reset(self) -> None:
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.is_speaking = False
        self.speech_frames = 0
        self.silence_frames = 0


class SileroVADProvider(BaseVADProvider):
    """Production-grade, lazy-loaded Silero ONNX Voice Activity Detector."""

    def __init__(self, config: SileroVADConfig | None = None) -> None:
        self.config = config or SileroVADConfig()
        self._session: Any | None = None
        self._session_states: dict[str, _SessionState] = {}
        self._initialized: bool = False
        self._initialization_error: str | None = None

    def is_available(self) -> bool:
        """Checks whether ONNX runtime is installed and model file exists on disk."""
        if not os.path.exists(self.config.model_path):
            return False
        try:
            import onnxruntime  # noqa: F401
            return True
        except ImportError:
            return False

    def validate_model_integrity(self) -> None:
        """Validates that model file exists and matches expected SHA-256 if configured."""
        if not os.path.exists(self.config.model_path):
            raise SileroModelIntegrityError(
                f"Silero VAD model file not found at '{self.config.model_path}'. "
                "Run 'python scripts/bootstrap_models.py' to download."
            )

        if self.config.expected_sha256:
            sha256 = hashlib.sha256()
            with open(self.config.model_path, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
            actual_hash = sha256.hexdigest().lower()
            if actual_hash != self.config.expected_sha256.lower():
                raise SileroModelIntegrityError(
                    f"Silero model SHA-256 mismatch. Expected {self.config.expected_sha256}, got {actual_hash}."
                )

    def initialize(self) -> None:
        """Lazily initializes the ONNX runtime inference session."""
        if self._initialized:
            return

        self.validate_model_integrity()

        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            # Use CPUExecutionProvider exclusively for lightweight, deterministic execution
            self._session = ort.InferenceSession(
                self.config.model_path,
                sess_options=opts,
                providers=["CPUExecutionProvider"]
            )
            self._initialized = True
            logger.info("Silero ONNX VAD session initialized successfully.")
        except ImportError as err:
            self._initialization_error = "onnxruntime package not installed"
            raise PixelException(
                message="onnxruntime is required for SileroVADProvider. Install with 'pip install onnxruntime'.",
                category=ErrorCategory.PROVIDER_ERROR,
                code="ONNXRUNTIME_MISSING"
            ) from err
        except Exception as err:
            self._initialization_error = str(err)
            raise PixelException(
                message=f"Failed to load Silero ONNX model: {err}",
                category=ErrorCategory.PROVIDER_ERROR,
                code="SILERO_LOAD_FAILURE"
            ) from err

    def _get_or_create_session_state(self, session_id: str) -> _SessionState:
        if session_id not in self._session_states:
            self._session_states[session_id] = _SessionState(sample_rate=self.config.sample_rate)
        return self._session_states[session_id]

    def reset(self, session_id: str) -> None:
        """Resets tracking state and recurrent tensors for an active session."""
        if session_id in self._session_states:
            self._session_states[session_id].reset()

    async def shutdown(self) -> None:
        """Releases the ONNX session and state cache."""
        self._session = None
        self._session_states.clear()
        self._initialized = False
        logger.info("Silero ONNX VAD provider shut down.")

    async def process_frame(self, frame: AudioFrame, session_id: str) -> VADEvent:
        """Runs VAD inference on a canonical PCM AudioFrame and emits a VADEvent."""
        if not self._initialized:
            self.initialize()

        if self._session is None:
            raise PixelException(
                message="Silero VAD session is not initialized",
                category=ErrorCategory.PROVIDER_ERROR,
                code="SILERO_SESSION_NULL"
            )

        # 1. Convert PCM int16 bytes to normalized float32 array (-1.0 to 1.0)
        audio_int16 = np.frombuffer(frame.pcm_data, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        # 2. Compute audio energy level in dB for telemetry
        rms = np.sqrt(np.mean(audio_float32**2)) if len(audio_float32) > 0 else 0.0
        energy_db = float(20 * np.log10(rms)) if rms > 1e-6 else -60.0

        # 3. Retrieve session context state
        sess_state = self._get_or_create_session_state(session_id)
        sr_tensor = np.array(self.config.sample_rate, dtype=np.int64)

        # 4. Execute ONNX Inference over 512-sample windows
        window_size = self.config.window_size_samples
        speech_prob = 0.0

        if len(audio_float32) == 0:
            vad_state = self._evaluate_transitions(sess_state, 0.0)
            return VADEvent(
                session_id=session_id,
                state=vad_state,
                speech_probability=0.0,
                energy_level_db=-60.0
            )

        # Slice into window_size chunks
        for i in range(0, len(audio_float32), window_size):
            chunk = audio_float32[i : i + window_size]
            if len(chunk) < window_size:
                chunk = np.pad(chunk, (0, window_size - len(chunk)))

            input_tensor = np.expand_dims(chunk, axis=0)
            ort_inputs = {
                "input": input_tensor,
                "state": sess_state.state,
                "sr": sr_tensor
            }
            ort_outputs = self._session.run(None, ort_inputs)
            chunk_prob = float(np.array(ort_outputs[0]).flatten()[0])
            sess_state.state = ort_outputs[1]  # Update recurrent state tensor
            speech_prob = max(speech_prob, chunk_prob)

        # 5. Stateful smoothing & state transitions
        vad_state = self._evaluate_transitions(sess_state, speech_prob)

        return VADEvent(
            session_id=session_id,
            state=vad_state,
            speech_probability=speech_prob,
            energy_level_db=energy_db
        )

    def _evaluate_transitions(self, state: _SessionState, speech_prob: float) -> VADState:
        """Applies onset and hangover thresholds to determine state transitions."""
        frame_duration_ms = (self.config.window_size_samples / self.config.sample_rate) * 1000
        min_speech_frames = max(1, int(self.config.min_speech_duration_ms / frame_duration_ms))
        min_silence_frames = max(1, int(self.config.min_silence_duration_ms / frame_duration_ms))

        if speech_prob >= self.config.threshold:
            state.speech_frames += 1
            state.silence_frames = 0
            if not state.is_speaking:
                if state.speech_frames >= min_speech_frames:
                    state.is_speaking = True
                    return VADState.SPEECH_START
                return VADState.SILENCE
            return VADState.SPEECH_CONTINUING

        elif speech_prob < self.config.neg_threshold:
            state.silence_frames += 1
            state.speech_frames = 0
            if state.is_speaking:
                if state.silence_frames >= min_silence_frames:
                    state.is_speaking = False
                    return VADState.SPEECH_END
                return VADState.SPEECH_CONTINUING
            return VADState.SILENCE

        else:
            # Hysteresis band between neg_threshold and threshold
            if state.is_speaking:
                return VADState.SPEECH_CONTINUING
            return VADState.SILENCE
