"""Embedding stub + cosine + pgvector text serialization tests."""

from __future__ import annotations

import pytest
from adhkar.ai.embeddings import (
    EmbeddingRouter,
    StubEmbedder,
    cosine,
    to_pgvector_text,
)


@pytest.mark.asyncio
async def test_stub_embedder_dim_and_normalization() -> None:
    e = StubEmbedder()
    r = await e.embed("the quick brown fox")
    assert r.dimension == 128
    assert len(r.vector) == 128
    # L2-normalized: ||v|| ≈ 1
    norm = sum(v * v for v in r.vector) ** 0.5
    assert 0.99 < norm < 1.01


@pytest.mark.asyncio
async def test_same_text_yields_identical_embedding() -> None:
    e = StubEmbedder()
    a = await e.embed("phishing campaign acme")
    b = await e.embed("phishing campaign acme")
    assert a.vector == b.vector


@pytest.mark.asyncio
async def test_similar_texts_have_higher_cosine_than_unrelated() -> None:
    e = StubEmbedder()
    base = (await e.embed("phishing email acme corp")).vector
    near = (await e.embed("phishing email acme")).vector
    far = (await e.embed("server reboot scheduled")).vector
    assert cosine(base, near) > cosine(base, far)


def test_cosine_is_one_for_identical_vectors() -> None:
    v = [1.0, 2.0, 3.0]
    assert 0.999 < cosine(v, v) < 1.001


def test_cosine_is_zero_for_orthogonal_vectors() -> None:
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert abs(cosine(a, b)) < 1e-6


def test_pgvector_text_format() -> None:
    s = to_pgvector_text([0.1, 0.25, -0.5])
    assert s.startswith("[") and s.endswith("]")
    assert "0.100000" in s
    assert "-0.500000" in s


@pytest.mark.asyncio
async def test_embedding_router_rejects_unknown_provider() -> None:
    r = EmbeddingRouter()
    with pytest.raises(ValueError, match="unknown_embedding_provider"):
        await r.embed("x", provider="not-real")
