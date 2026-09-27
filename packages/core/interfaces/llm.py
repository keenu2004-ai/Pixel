"""Base Local LLM Provider Interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from packages.contracts.models import (
    LocalLLMRequest,
    LocalLLMResponse,
    ModelLifecycleState,
    ModelMetadata,
)


class BaseLocalLLMProvider(ABC):
    """Abstract interface for local quantized neural language models."""

    @abstractmethod
    def load_model(self, metadata: ModelMetadata) -> bool:
        """Load and initialize model weights into memory/GPU."""
        raise NotImplementedError

    @abstractmethod
    def unload_model(self) -> bool:
        """Unload model and release memory/VRAM resources."""
        raise NotImplementedError

    @abstractmethod
    async def generate_response(self, request: LocalLLMRequest) -> LocalLLMResponse:
        """Perform full inference and return complete response with tool calls."""
        raise NotImplementedError

    @abstractmethod
    def generate_response_stream(self, request: LocalLLMRequest) -> AsyncIterator[str]:
        """Stream generated text tokens incrementally."""
        raise NotImplementedError

    @abstractmethod
    def get_state(self) -> ModelLifecycleState:
        """Return current lifecycle state."""
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self) -> ModelMetadata | None:
        """Return metadata of currently loaded model."""
        raise NotImplementedError
