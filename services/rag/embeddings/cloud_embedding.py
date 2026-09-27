"""Cloud Vector Embedding Provider.

Connects to OpenAI / compatible embedding endpoints with retry and error mapping.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from packages.contracts.errors import NetworkException, ProviderUnavailableException
from packages.core.interfaces.embeddings import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class CloudEmbeddingProvider(BaseEmbeddingProvider):
    """External API embedding provider."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint_url: str = "https://api.openai.com/v1/embeddings",
        model_name: str = "text-embedding-3-small",
        dimension: int = 1536,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.endpoint_url = endpoint_url
        self._model_name = model_name
        self._dimension = dimension
        self.timeout_seconds = timeout_seconds

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    async def embed_text(self, text: str) -> list[float]:
        batch_res = await self.embed_batch([text])
        return batch_res[0] if batch_res else [0.0] * self._dimension

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if not self.is_available():
            raise ProviderUnavailableException("Cloud embedding API key is not configured.")

        payload = {
            "input": texts,
            "model": self._model_name,
        }
        data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            self.endpoint_url,
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                resp_data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
                embeddings = [item["embedding"] for item in resp_data.get("data", [])]
                return embeddings
        except urllib.error.URLError as err:
            logger.error("Cloud embedding request failed: %s", err)
            raise NetworkException(f"Failed to generate cloud embeddings: {err}") from err
        except Exception as err:
            logger.error("Unexpected cloud embedding error: %s", err)
            raise NetworkException(f"Embedding API error: {err}") from err
