"""Deterministic Feature-Hash Embedding Provider.

Generates reproducible, normalized dense embeddings locally without network latency or external model weights.
"""

import hashlib
import math
import re

from packages.core.interfaces.embeddings import BaseEmbeddingProvider


class DeterministicHashEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic local embedding generator for testing and offline semantic indexing."""

    def __init__(self, dimension: int = 384, model_name: str = "hash-embed-v1") -> None:
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed_text(self, text: str) -> list[float]:
        """Maps text to a normalized dense vector using feature hashing."""
        vec = [0.0] * self._dimension
        # Tokenize words cleanly
        words = re.findall(r"[a-z0-9]+", text.lower())
        if not words:
            return vec

        # 1. Unigram & Bigram hashing
        for i, word in enumerate(words):
            # Unigram
            h1 = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % self._dimension
            sign1 = 1.0 if (h1 % 2 == 0) else -1.0
            vec[h1] += sign1 * 2.0

            # Bigram
            if i > 0:
                bigram = f"{words[i - 1]}_{word}"
                h2 = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest(), 16) % self._dimension
                sign2 = 1.0 if (h2 % 2 == 0) else -1.0
                vec[h2] += sign2 * 2.5

            # Subword 3-grams for partial matching (e.g. whisper in fasterwhisper)
            if len(word) >= 4:
                for j in range(len(word) - 2):
                    trigram = word[j : j + 3]
                    h3 = int(hashlib.md5(trigram.encode("utf-8")).hexdigest(), 16) % self._dimension
                    sign3 = 1.0 if (h3 % 2 == 0) else -1.0
                    vec[h3] += sign3 * 0.5

        # 2. L2 Normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            return [x / norm for x in vec]
        return vec

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_text(t) for t in texts]
