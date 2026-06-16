"""Unit tests for the CSV parsing helpers in observable_import."""

from __future__ import annotations

from adhkar.api.v1.observable_import import _parse_bool, _split_tags


def test_parse_bool_recognizes_truthy_aliases() -> None:
    for v in ("1", "true", "TRUE", "yes", "y", "t", "  True  "):
        assert _parse_bool(v) is True


def test_parse_bool_returns_false_for_everything_else() -> None:
    for v in ("0", "false", "no", "", "n", "f", "maybe"):
        assert _parse_bool(v) is False


def test_split_tags_handles_commas_and_whitespace() -> None:
    assert _split_tags(" phish , acme , ") == ["phish", "acme"]


def test_split_tags_returns_empty_for_blank() -> None:
    assert _split_tags("") == []
    assert _split_tags("   ") == []
