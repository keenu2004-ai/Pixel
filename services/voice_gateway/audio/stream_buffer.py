"""Bounded, Async-Safe Audio Stream Buffer for L0/L1 Audio Pipelines."""

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from enum import StrEnum

from packages.contracts.events import AudioFrame


class AudioFormatError(ValueError):
    """Raised when an incoming audio frame violates the canonical audio contract."""

    pass


class BufferOverflowError(RuntimeError):
    """Raised when the buffer exceeds max capacity under RAISE_ON_OVERFLOW strategy."""

    pass


class OverflowStrategy(StrEnum):
    """Backpressure handling strategy when audio buffer is saturated."""

    DROP_OLDEST = "DROP_OLDEST"  # Drops oldest buffered frames to prioritize low latency
    RAISE_ON_OVERFLOW = "RAISE_ON_OVERFLOW"  # Raises BufferOverflowError immediately
    BLOCK = "BLOCK"  # Blocks producer until space becomes available


class AudioStreamBuffer:
    """Bounded, thread-safe async FIFO audio buffer with backpressure and format validation.

    Canonical Format Constraints:
    - PCM 16-bit Mono (1 channel)
    - 16,000 Hz Sample Rate
    - Even byte count (2 bytes per sample)
    """

    CANONICAL_SAMPLE_RATE: int = 16000
    CANONICAL_CHANNELS: int = 1
    BYTES_PER_SAMPLE: int = 2

    def __init__(
        self,
        max_frames: int = 100,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB default safety ceiling
        overflow_strategy: OverflowStrategy = OverflowStrategy.DROP_OLDEST,
    ) -> None:
        if max_frames <= 0:
            raise ValueError("max_frames must be a positive integer")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")

        self.max_frames = max_frames
        self.max_bytes = max_bytes
        self.overflow_strategy = overflow_strategy

        self._queue: deque[AudioFrame] = deque()
        self._current_bytes: int = 0
        self._closed: bool = False
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._not_full = asyncio.Condition(self._lock)

        # Telemetry & metrics
        self.total_pushed_frames: int = 0
        self.total_dropped_frames: int = 0

    @classmethod
    def validate_frame_format(cls, frame: AudioFrame) -> None:
        """Validates that the given frame complies with canonical PCM 16kHz Mono specification."""
        if frame.sample_rate != cls.CANONICAL_SAMPLE_RATE:
            raise AudioFormatError(
                f"Unsupported sample rate: {frame.sample_rate}Hz. Expected {cls.CANONICAL_SAMPLE_RATE}Hz."
            )
        if frame.channels != cls.CANONICAL_CHANNELS:
            raise AudioFormatError(
                f"Unsupported channel count: {frame.channels}. Expected {cls.CANONICAL_CHANNELS} (mono)."
            )
        if len(frame.pcm_data) == 0:
            raise AudioFormatError("Audio frame contains empty PCM data.")
        if len(frame.pcm_data) % cls.BYTES_PER_SAMPLE != 0:
            raise AudioFormatError(
                f"PCM data byte length {len(frame.pcm_data)} is not aligned to 16-bit samples (2 bytes/sample)."
            )

    @property
    def is_closed(self) -> bool:
        """Returns True if the buffer has been closed for new incoming frames."""
        return self._closed

    @property
    def buffered_frames_count(self) -> int:
        """Returns current number of queued frames."""
        return len(self._queue)

    @property
    def buffered_bytes(self) -> int:
        """Returns current volume of queued PCM data in bytes."""
        return self._current_bytes

    async def push(self, frame: AudioFrame) -> bool:
        """Pushes an audio frame into the buffer applying validation and overflow strategy.

        Returns True if the frame was buffered, False if buffer was closed.
        """
        self.validate_frame_format(frame)
        frame_size = len(frame.pcm_data)

        async with self._lock:
            if self._closed:
                return False

            # Check capacity limits
            while (
                len(self._queue) >= self.max_frames
                or self._current_bytes + frame_size > self.max_bytes
            ):
                if self.overflow_strategy == OverflowStrategy.DROP_OLDEST:
                    if self._queue:
                        dropped = self._queue.popleft()
                        self._current_bytes -= len(dropped.pcm_data)
                        self.total_dropped_frames += 1
                    else:
                        # Single frame exceeds max_bytes
                        raise BufferOverflowError("Frame exceeds total buffer capacity.")
                elif self.overflow_strategy == OverflowStrategy.RAISE_ON_OVERFLOW:
                    raise BufferOverflowError("AudioStreamBuffer saturated.")
                elif self.overflow_strategy == OverflowStrategy.BLOCK:
                    await self._not_full.wait()
                    if self._closed:
                        return False

            self._queue.append(frame)
            self._current_bytes += frame_size
            self.total_pushed_frames += 1

            self._not_empty.notify()
            return True

    async def pop(self, timeout: float | None = None) -> AudioFrame | None:
        """Pops the next FIFO AudioFrame.

        Returns None if buffer is closed and empty, or raises TimeoutError if timeout expires.
        """
        async with self._lock:
            while not self._queue:
                if self._closed:
                    return None
                try:
                    if timeout is not None:
                        await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
                    else:
                        await self._not_empty.wait()
                except TimeoutError as err:
                    raise TimeoutError("Timed out waiting for audio frame.") from err

            frame = self._queue.popleft()
            self._current_bytes -= len(frame.pcm_data)
            self._not_full.notify()
            return frame

    async def stream(self) -> AsyncIterator[AudioFrame]:
        """Async generator streaming frames from the buffer until closed and drained."""
        while True:
            frame = await self.pop()
            if frame is None:
                break
            yield frame

    async def close(self) -> None:
        """Closes the buffer. No new frames can be pushed; existing frames can be consumed."""
        async with self._lock:
            self._closed = True
            self._not_empty.notify_all()
            self._not_full.notify_all()

    async def clear(self) -> None:
        """Clears all buffered frames and resets byte counter."""
        async with self._lock:
            self._queue.clear()
            self._current_bytes = 0
            self._not_full.notify_all()
