"""Embeddings: pluggable provider with a deterministic stub for offline runs.

The stub hashes tokens into a fixed-dimension float vector so similarity
search behaves consistently in dev/test. Production deployments swap in
the OpenAI/Anthropic embedding providers via EmbeddingRouter."""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True, slots=True)
class EmbedResult:
    model: str
    dimension: int
    vector: list[float]


def to_pgvector_text(vec: list[float]) -> str:
    """Serialize a float vector into pgvector's text format."""
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


class EmbeddingProvider(ABC):
    name: str

    @abstractmethod
    async def embed(self, text: str) -> EmbedResult: ...


class StubEmbedder(EmbeddingProvider):
    """Deterministic hash-bag embedder. dim=128. L2-normalized."""

    name = "stub-embed-128"
    _dim = 128

    async def embed(self, text: str) -> EmbedResult:
        vec = [0.0] * self._dim
        for tok in _TOKEN_RE.findall((text or "").lower()):
            h = int.from_bytes(hashlib.sha256(tok.encode("utf-8")).digest()[:4], "big")
            idx = h % self._dim
            sign = 1.0 if (h >> 31) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vec = [v / norm for v in vec]
        return EmbedResult(model=self.name, dimension=self._dim, vector=vec)


class EmbeddingRouter:
    def __init__(self, default: str = "stub-embed-128") -> None:
        self._providers: dict[str, EmbeddingProvider] = {}
        self._default = default
        self.register(StubEmbedder())

    def register(self, p: EmbeddingProvider) -> None:
        self._providers[p.name] = p

    async def embed(self, text: str, provider: str | None = None) -> EmbedResult:
        name = provider or self._default
        if name not in self._providers:
            raise ValueError(f"unknown_embedding_provider:{name}")
        return await self._providers[name].embed(text)


_router: EmbeddingRouter | None = None


def get_embedding_router() -> EmbeddingRouter:
    global _router
    if _router is None:
        _router = EmbeddingRouter()
    return _router


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity for assembled vectors. -1..1."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
