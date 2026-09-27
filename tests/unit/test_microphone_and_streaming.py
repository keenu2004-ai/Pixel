"""Unit tests for Real Microphone Capture Runtime and Audio Buffering."""

import pytest

from packages.contracts.runtime import AudioStreamConfig
from services.voice_gateway.audio.microphone_runtime import MicrophoneRuntime


@pytest.mark.asyncio
async def test_microphone_runtime_start_stop() -> None:
    config = AudioStreamConfig(sample_rate=16000, chunk_size_samples=512)
    mic = MicrophoneRuntime(config=config, buffer_size_frames=50)

    assert not mic.is_capturing

    # Start capture with synthetic frames
    synthetic_chunks = [b"\x00\x01" * 512, b"\x00\x02" * 512, b"\x00\x03" * 512]
    await mic.start_capture(simulated_frames=synthetic_chunks)
    assert mic.is_capturing

    # Consume frames
    collected = []
    async for frame in mic.stream_frames():
        collected.append(frame)
        if len(collected) == len(synthetic_chunks):
            break

    assert len(collected) == 3
    assert collected[0].sample_rate == 16000
    assert collected[0].channels == 1

    await mic.stop_capture()
    assert not mic.is_capturing


@pytest.mark.asyncio
async def test_microphone_direct_frame_injection() -> None:
    mic = MicrophoneRuntime()
    await mic.start_capture()

    test_frame = b"\xaa\xbb" * 512
    await mic.inject_frame(test_frame)

    async for frame in mic.stream_frames():
        assert frame.pcm_data == test_frame
        break

    await mic.stop_capture()
