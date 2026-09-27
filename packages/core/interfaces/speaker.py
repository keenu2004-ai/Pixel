"""Base Speaker Encoder and Voice Identity Interface."""

from abc import ABC, abstractmethod

from packages.contracts.models import (
    SpeakerEnrollmentRequest,
    SpeakerProfile,
    SpeakerVerificationResult,
)


class BaseSpeakerEncoder(ABC):
    """Abstract interface for neural speaker embedding extraction and verification."""

    @abstractmethod
    def encode_embedding(self, audio_samples: list[bytes], sample_rate: int = 16000) -> list[float]:
        """Extract a normalized speaker embedding vector from one or more PCM audio samples."""
        raise NotImplementedError

    @abstractmethod
    def compute_similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """Compute cosine similarity between two speaker embeddings."""
        raise NotImplementedError

    @abstractmethod
    def verify_speaker(
        self,
        sample: bytes,
        profile: SpeakerProfile,
        threshold: float = 0.75,
        sample_rate: int = 16000,
    ) -> SpeakerVerificationResult:
        """Verify if an audio sample matches an enrolled speaker profile."""
        raise NotImplementedError

    @abstractmethod
    def enroll_speaker(self, request: SpeakerEnrollmentRequest) -> SpeakerProfile:
        """Process an authorized enrollment request and construct a persistent SpeakerProfile."""
        raise NotImplementedError
