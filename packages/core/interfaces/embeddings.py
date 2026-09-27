"""Abstract Interface for Vector Embedding Providers."""

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Abstract base provider for text embedding generation."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the vector dimensionality (e.g. 384, 768, 1536)."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the canonical model identifier."""
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generates dense embedding vector for a single text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generates dense embedding vectors for a batch of texts."""
        pass
