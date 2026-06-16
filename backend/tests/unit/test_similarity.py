"""Similarity endpoint helper tests (no DB) + ranking smoke."""

from __future__ import annotations

from adhkar.api.v1.similarity import _parse_pgvector_text


def test_parse_pgvector_text_json() -> None:
    assert _parse_pgvector_text("[1.0,2.0,3.0]") == [1.0, 2.0, 3.0]


def test_parse_pgvector_text_pgvector_format() -> None:
    assert _parse_pgvector_text("[0.100000,0.250000,-0.500000]") == [0.1, 0.25, -0.5]


def test_parse_pgvector_text_handles_empty() -> None:
    assert _parse_pgvector_text("[]") == []
