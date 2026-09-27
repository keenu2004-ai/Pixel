"""Unit tests for AudioStreamBuffer format validation, backpressure, and async streaming."""

import asyncio

import pytest

from packages.contracts.events import AudioFrame
from services.voice_gateway.audio.stream_buffer import (
    AudioFormatError,
    AudioStreamBuffer,
    BufferOverflowError,
    OverflowStrategy,
)


def _create_frame(sample_rate: int = 16000, channels: int = 1, num_samples: int = 512) -> AudioFrame:
    # 512 16-bit samples = 1024 bytes (32ms frame @ 16kHz)
    pcm_data = b"\x00\x01" * num_samples
    return AudioFrame(
        sample_rate=sample_rate,
        channels=channels,
        pcm_data=pcm_data,
        timestamp_ms=1000
    )


@pytest.mark.asyncio
async def test_buffer_push_pop_fifo() -> None:
    buffer = AudioStreamBuffer(max_frames=10)
    frame1 = _create_frame(num_samples=100)
    frame2 = _create_frame(num_samples=200)

    await buffer.push(frame1)
    await buffer.push(frame2)

    assert buffer.buffered_frames_count == 2
    assert buffer.buffered_bytes == len(frame1.pcm_data) + len(frame2.pcm_data)

    popped1 = await buffer.pop()
    assert popped1 == frame1
    assert buffer.buffered_frames_count == 1

    popped2 = await buffer.pop()
    assert popped2 == frame2
    assert buffer.buffered_frames_count == 0


@pytest.mark.asyncio
async def test_format_validation_rejections() -> None:
    buffer = AudioStreamBuffer()

    # Wrong sample rate
    with pytest.raises(AudioFormatError, match="Unsupported sample rate"):
        await buffer.push(_create_frame(sample_rate=44100))

    # Stereo audio (channels=2)
    with pytest.raises(AudioFormatError, match="Unsupported channel count"):
        await buffer.push(_create_frame(channels=2))

    # Empty PCM data
    with pytest.raises(AudioFormatError, match="empty PCM data"):
        await buffer.push(AudioFrame(sample_rate=16000, channels=1, pcm_data=b"", timestamp_ms=0))

    # Odd byte count (not 16-bit aligned)
    with pytest.raises(AudioFormatError, match="not aligned"):
        await buffer.push(AudioFrame(sample_rate=16000, channels=1, pcm_data=b"\x01\x02\x03", timestamp_ms=0))


@pytest.mark.asyncio
async def test_overflow_strategy_drop_oldest() -> None:
    buffer = AudioStreamBuffer(max_frames=2, overflow_strategy=OverflowStrategy.DROP_OLDEST)
    f1 = _create_frame(num_samples=10)
    f2 = _create_frame(num_samples=20)
    f3 = _create_frame(num_samples=30)

    await buffer.push(f1)
    await buffer.push(f2)
    # Exceeds max_frames -> drops f1
    await buffer.push(f3)

    assert buffer.buffered_frames_count == 2
    assert buffer.total_dropped_frames == 1

    popped = await buffer.pop()
    assert popped == f2
    popped = await buffer.pop()
    assert popped == f3


@pytest.mark.asyncio
async def test_overflow_strategy_raise() -> None:
    buffer = AudioStreamBuffer(max_frames=2, overflow_strategy=OverflowStrategy.RAISE_ON_OVERFLOW)
    await buffer.push(_create_frame())
    await buffer.push(_create_frame())

    with pytest.raises(BufferOverflowError):
        await buffer.push(_create_frame())


@pytest.mark.asyncio
async def test_overflow_strategy_block_and_unblock_on_pop() -> None:
    buffer = AudioStreamBuffer(max_frames=1, overflow_strategy=OverflowStrategy.BLOCK)
    f1 = _create_frame(num_samples=10)
    f2 = _create_frame(num_samples=20)

    await buffer.push(f1)

    # Producer tries to push when buffer is full
    push_task = asyncio.create_task(buffer.push(f2))
    await asyncio.sleep(0.01)
    assert not push_task.done()

    # Consumer pops f1 -> buffer unblocks and f2 is accepted
    popped = await buffer.pop()
    assert popped == f1
    res = await push_task
    assert res is True
    assert buffer.buffered_frames_count == 1


@pytest.mark.asyncio
async def test_overflow_strategy_block_unblock_on_close() -> None:
    buffer = AudioStreamBuffer(max_frames=1, overflow_strategy=OverflowStrategy.BLOCK)
    f1 = _create_frame(num_samples=10)
    f2 = _create_frame(num_samples=20)

    await buffer.push(f1)

    # Producer blocks on full buffer
    push_task = asyncio.create_task(buffer.push(f2))
    await asyncio.sleep(0.01)
    assert not push_task.done()

    # Close buffer -> blocked push safely wakes up and returns False (no deadlock)
    await buffer.close()
    res = await push_task
    assert res is False


@pytest.mark.asyncio
async def test_buffer_close_and_stream() -> None:
    buffer = AudioStreamBuffer()
    f1 = _create_frame(num_samples=50)
    f2 = _create_frame(num_samples=50)

    await buffer.push(f1)
    await buffer.push(f2)
    await buffer.close()

    assert buffer.is_closed is True

    # Pushing after close returns False
    accepted = await buffer.push(_create_frame())
    assert accepted is False

    # Stream yields remaining buffered frames then terminates
    streamed = []
    async for frame in buffer.stream():
        streamed.append(frame)

    assert streamed == [f1, f2]


@pytest.mark.asyncio
async def test_pop_timeout() -> None:
    buffer = AudioStreamBuffer()
    with pytest.raises(TimeoutError):
        await buffer.pop(timeout=0.05)


@pytest.mark.asyncio
async def test_clear_buffer() -> None:
    buffer = AudioStreamBuffer()
    await buffer.push(_create_frame())
    assert buffer.buffered_frames_count == 1

    await buffer.clear()
    assert buffer.buffered_frames_count == 0
    assert buffer.buffered_bytes == 0
