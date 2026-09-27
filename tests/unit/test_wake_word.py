"""Unit tests for OpenWakeWordProvider multi-phrase wake detection and cooldown logic."""

import os
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from packages.contracts.events import AudioFrame
from services.voice_gateway.wake.openwakeword_provider import (
    OpenWakeWordConfig,
    OpenWakeWordProvider,
    WakeWordModelIntegrityError,
)


def _create_frame(num_samples: int = 640) -> AudioFrame:
    # 640 samples = 40ms @ 16kHz
    return AudioFrame(
        sample_rate=16000, channels=1, pcm_data=b"\x00\x01" * num_samples, timestamp_ms=1000
    )


def test_openwakeword_lazy_init() -> None:
    config = OpenWakeWordConfig(model_paths={"hey_pixel": "non_existent.onnx"})
    provider = OpenWakeWordProvider(config)
    assert provider.is_available() is False
    assert provider.get_supported_phrases() == ["hey_pixel"]
    assert provider._initialized is False


def test_missing_model_raises_integrity_error() -> None:
    config = OpenWakeWordConfig(model_paths={"hey_pixel": "missing.onnx"})
    provider = OpenWakeWordProvider(config)
    with pytest.raises(
        WakeWordModelIntegrityError, match="Wake word model for 'hey_pixel' not found"
    ):
        provider.validate_model_integrity()


def test_checksum_mismatch_raises_integrity_error(tmp_path: os.PathLike[str]) -> None:
    path = os.path.join(tmp_path, "fake_wake.onnx")
    with open(path, "wb") as f:
        f.write(b"fake_model_bytes")

    config = OpenWakeWordConfig(
        model_paths={"hey_pixel": path},
        expected_sha256={
            "hey_pixel": "0000000000000000000000000000000000000000000000000000000000000000"
        },
    )
    provider = OpenWakeWordProvider(config)
    with pytest.raises(WakeWordModelIntegrityError, match="Checksum mismatch"):
        provider.validate_model_integrity()


@pytest.mark.asyncio
async def test_wake_detection_trigger_and_cooldown() -> None:
    config = OpenWakeWordConfig(
        model_paths={"hey_pixel": "fake.onnx"},
        threshold=0.6,
        cooldown_seconds=1.0,
        chunk_samples=1280,
    )
    provider = OpenWakeWordProvider(config)

    # Mock ONNX session
    mock_session = MagicMock()
    mock_input_meta = MagicMock()
    mock_input_meta.name = "input_audio"
    mock_session.get_inputs.return_value = [mock_input_meta]

    # Return low probability 0.1 first, then 0.95
    mock_session.run.return_value = [np.array([0.1], dtype=np.float32)]
    provider._sessions = {"hey_pixel": mock_session}
    provider._initialized = True

    # Frame 1: 640 samples -> buffer not yet 1280 samples -> None
    ev1 = await provider.process_frame(_create_frame(640), session_id="s1")
    assert ev1 is None

    # Frame 2: 640 samples -> total 1280 samples -> score 0.1 < threshold 0.6 -> None
    ev2 = await provider.process_frame(_create_frame(640), session_id="s1")
    assert ev2 is None

    # Frame 3: Model score spikes to 0.95 -> Triggers WakeEvent
    mock_session.run.return_value = [np.array([0.95], dtype=np.float32)]
    ev3 = await provider.process_frame(_create_frame(1280), session_id="s1")
    assert ev3 is not None
    assert ev3.phrase == "Hey Pixel"
    assert ev3.confidence == pytest.approx(0.95, abs=1e-2)

    # Frame 4: Sent immediately after trigger -> blocked by cooldown -> None
    ev4 = await provider.process_frame(_create_frame(1280), session_id="s1")
    assert ev4 is None

    # After cooldown expires -> can trigger again
    provider._session_states["s1"].last_trigger_time = time.time() - 2.0
    ev5 = await provider.process_frame(_create_frame(1280), session_id="s1")
    assert ev5 is not None
    assert ev5.phrase == "Hey Pixel"


@pytest.mark.asyncio
async def test_shutdown_cleanup() -> None:
    config = OpenWakeWordConfig(model_paths={"hey_pixel": "fake.onnx"})
    provider = OpenWakeWordProvider(config)
    provider._sessions = {"hey_pixel": MagicMock()}
    provider._initialized = True
    provider._get_or_create_session_state("s1")

    await provider.shutdown()
    assert len(provider._sessions) == 0
    assert len(provider._session_states) == 0
    assert provider._initialized is False
