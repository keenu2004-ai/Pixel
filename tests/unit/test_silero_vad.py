"""Unit tests for SileroVADProvider lifecycle, integrity checks, and state transitions."""

import os
from unittest.mock import MagicMock

import numpy as np
import pytest

from packages.contracts.events import AudioFrame, VADState
from services.voice_gateway.vad.silero_vad import (
    SileroModelIntegrityError,
    SileroVADConfig,
    SileroVADProvider,
)


def _create_pcm_frame(num_samples: int = 512) -> AudioFrame:
    # 512 16-bit samples = 1024 bytes (32ms frame @ 16kHz)
    pcm_bytes = b"\x00\x00" * num_samples
    return AudioFrame(sample_rate=16000, channels=1, pcm_data=pcm_bytes, timestamp_ms=1000)


def test_silero_vad_lazy_construction() -> None:
    config = SileroVADConfig(model_path="non_existent.onnx")
    provider = SileroVADProvider(config)
    assert provider.is_available() is False
    assert provider._initialized is False


def test_missing_model_raises_integrity_error() -> None:
    config = SileroVADConfig(model_path="data/models/missing_model.onnx")
    provider = SileroVADProvider(config)
    with pytest.raises(SileroModelIntegrityError, match="model file not found"):
        provider.validate_model_integrity()


def test_checksum_mismatch_raises_integrity_error(tmp_path: os.PathLike[str]) -> None:
    model_file = os.path.join(tmp_path, "fake_silero.onnx")
    with open(model_file, "wb") as f:
        f.write(b"fake ONNX bytes")

    config = SileroVADConfig(
        model_path=model_file,
        expected_sha256="0000000000000000000000000000000000000000000000000000000000000000",
    )
    provider = SileroVADProvider(config)
    with pytest.raises(SileroModelIntegrityError, match="SHA-256 mismatch"):
        provider.validate_model_integrity()


@pytest.mark.asyncio
async def test_mocked_vad_speech_state_transitions() -> None:
    config = SileroVADConfig(
        model_path="fake_model.onnx", min_speech_duration_ms=64, min_silence_duration_ms=64
    )
    provider = SileroVADProvider(config)

    # Mock ONNX session output
    mock_session = MagicMock()
    # Return speech probability 0.9 on speech, 0.1 on silence
    recurrent_state = np.zeros((2, 1, 128), dtype=np.float32)

    # Frame 1: Low probability -> SILENCE
    mock_session.run.return_value = [np.array([[[0.05]]], dtype=np.float32), recurrent_state]
    provider._session = mock_session
    provider._initialized = True

    f1 = _create_pcm_frame()
    ev1 = await provider.process_frame(f1, session_id="s1")
    assert ev1.state == VADState.SILENCE
    assert ev1.speech_probability == pytest.approx(0.05, abs=1e-3)

    # Frame 2: High probability (frame 1 of speech) -> SILENCE (waiting for min_speech_duration)
    mock_session.run.return_value = [np.array([[[0.92]]], dtype=np.float32), recurrent_state]
    ev2 = await provider.process_frame(f1, session_id="s1")
    assert ev2.state == VADState.SILENCE

    # Frame 3: High probability (frame 2 of speech) -> SPEECH_START
    ev3 = await provider.process_frame(f1, session_id="s1")
    assert ev3.state == VADState.SPEECH_START
    assert ev3.speech_probability == pytest.approx(0.92, abs=1e-3)

    # Frame 4: High probability -> SPEECH_CONTINUING
    ev4 = await provider.process_frame(f1, session_id="s1")
    assert ev4.state == VADState.SPEECH_CONTINUING

    # Frame 5: Low probability (frame 1 of silence) -> SPEECH_CONTINUING (hangover smoothing)
    mock_session.run.return_value = [np.array([[[0.10]]], dtype=np.float32), recurrent_state]
    ev5 = await provider.process_frame(f1, session_id="s1")
    assert ev5.state == VADState.SPEECH_CONTINUING

    # Frame 6: Low probability (frame 2 of silence) -> SPEECH_END
    ev6 = await provider.process_frame(f1, session_id="s1")
    assert ev6.state == VADState.SPEECH_END


@pytest.mark.asyncio
async def test_session_reset_and_shutdown() -> None:
    config = SileroVADConfig(model_path="fake_model.onnx")
    provider = SileroVADProvider(config)
    mock_session = MagicMock()
    mock_session.run.return_value = [
        np.array([[[0.95]]], dtype=np.float32),
        np.zeros((2, 1, 128), dtype=np.float32),
    ]
    provider._session = mock_session
    provider._initialized = True

    await provider.process_frame(_create_pcm_frame(), session_id="s1")
    assert "s1" in provider._session_states

    provider.reset(session_id="s1")
    assert provider._session_states["s1"].is_speaking is False
    assert provider._session_states["s1"].speech_frames == 0

    await provider.shutdown()
    assert provider._session is None
    assert provider._initialized is False
    assert len(provider._session_states) == 0
