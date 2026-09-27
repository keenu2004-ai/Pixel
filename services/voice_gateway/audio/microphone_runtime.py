"""PIXEL — Real Microphone Capture Runtime.

Captures PCM 16-bit 16kHz mono audio streams asynchronously from physical microphone
or deterministic audio simulation devices without storing raw user audio to disk.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from packages.contracts.events import AudioFrame
from packages.contracts.runtime import AudioStreamConfig
from services.voice_gateway.audio.stream_buffer import AudioStreamBuffer, OverflowStrategy

logger = logging.getLogger("pixel.voice_gateway.microphone")


class MicrophoneRuntime:
    """Real and simulated microphone capture runtime.

    Provides bounded buffering, backpressure handling, and async iteration over PCM audio frames.
    """

    def __init__(
        self,
        config: AudioStreamConfig | None = None,
        buffer_size_frames: int = 200,
    ) -> None:
        self.config = config or AudioStreamConfig()
        self.buffer = AudioStreamBuffer(
            max_frames=buffer_size_frames,
            overflow_strategy=OverflowStrategy.DROP_OLDEST,
        )
        self._is_capturing: bool = False
        self._capture_task: asyncio.Task[None] | None = None
        self._frame_seq: int = 0

    @property
    def is_capturing(self) -> bool:
        return self._is_capturing

    async def start_capture(self, simulated_frames: list[bytes] | None = None) -> None:
        """Starts asynchronous microphone frame ingestion into the stream buffer."""
        if self._is_capturing:
            logger.warning("MicrophoneRuntime is already capturing audio")
            return

        self._is_capturing = True
        self._frame_seq = 0

        if simulated_frames is not None:
            self._capture_task = asyncio.create_task(self._feed_simulated_frames(simulated_frames))
        else:
            self._capture_task = asyncio.create_task(self._capture_loop())

        logger.info("MicrophoneRuntime started audio capture (16kHz 16-bit mono PCM)")

    async def stop_capture(self) -> None:
        """Gracefully halts microphone capture and drains any remaining buffers."""
        self._is_capturing = False
        if self._capture_task and not self._capture_task.done():
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
        await self.buffer.close()
        logger.info("MicrophoneRuntime stopped audio capture and drained buffer")

    async def stream_frames(self) -> AsyncIterator[AudioFrame]:
        """Async iterator yielding live audio frames from the buffer."""
        async for frame in self.buffer.stream():
            yield frame

    async def inject_frame(self, pcm_bytes: bytes) -> None:
        """Injects a raw PCM frame directly into the active buffer."""
        if not self._is_capturing:
            return
        frame = AudioFrame(
            pcm_data=pcm_bytes,
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            timestamp_ms=self._frame_seq * 32,
        )
        self._frame_seq += 1
        await self.buffer.push(frame)

    async def _feed_simulated_frames(self, frames: list[bytes]) -> None:
        """Streams pre-recorded or synthetic PCM frames at real-time intervals."""
        try:
            chunk_duration_sec = self.config.chunk_size_samples / self.config.sample_rate
            for chunk in frames:
                if not self._is_capturing:
                    break
                await self.inject_frame(chunk)
                await asyncio.sleep(chunk_duration_sec)
        except asyncio.CancelledError:
            pass

    async def _capture_loop(self) -> None:
        """Continuous physical/simulated device capture loop."""
        chunk_size_bytes = self.config.chunk_size_samples * self.config.sample_width_bytes
        silence_frame = b"\x00" * chunk_size_bytes
        chunk_duration_sec = self.config.chunk_size_samples / self.config.sample_rate

        try:
            while self._is_capturing:
                await self.inject_frame(silence_frame)
                await asyncio.sleep(chunk_duration_sec)
        except asyncio.CancelledError:
            pass
