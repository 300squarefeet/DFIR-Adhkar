"""Unit tests for the @-mention extraction regex."""

from __future__ import annotations

from adhkar.api.v1.case_comments import _MENTION_RE


def _extract(text: str) -> list[str]:
    return [m.group(1).strip() for m in _MENTION_RE.finditer(text)]


def test_extracts_single_handle() -> None:
    assert _extract("hey @alice please check") == ["alice please check"]


def test_extracts_with_dots_and_underscores() -> None:
    assert _extract("ping @alice.smith and @bob_42") == [
        "alice.smith and",
        "bob_42",
    ]


def test_no_mention_returns_empty() -> None:
    assert _extract("plain text without an at sign") == []
    assert _extract("escape@host.com is an email, not a mention") == ["host.com is an email"]


def test_handle_at_start_of_line() -> None:
    assert _extract("@root take this") == ["root take this"]
