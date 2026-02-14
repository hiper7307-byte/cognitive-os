from __future__ import annotations

import hashlib
import math
from typing import List


class EmbeddingProvider:
    def __init__(self, model_name: str = "local-hash-384") -> None:
        self.model_name = model_name
        self.dim = 384

    def _hash_embed(self, text: str) -> List[float]:
        text = (text or "").strip()
        if not text:
            return [0.0] * self.dim

        vec = [0.0] * self.dim
        tokens = text.lower().split()

        for tok in tokens:
            h = hashlib.sha256(tok.encode("utf-8")).digest()
            for i in range(self.dim):
                vec[i] += (h[i % len(h)] / 255.0) - 0.5

        # l2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed(self, text: str) -> List[float]:
        return self._hash_embed(text)

    def embed_many(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_embed(t) for t in texts]


embedding_provider = EmbeddingProvider()
