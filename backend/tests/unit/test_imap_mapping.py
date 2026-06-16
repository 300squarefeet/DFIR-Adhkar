"""IMAP message → AlertPayload mapping tests (no network)."""

from __future__ import annotations

from adhkar.feeders.imap import _msg_to_payload


def _rfc822(subject: str, sender: str, msg_id: str, body: str) -> bytes:
    return (
        f"From: {sender}\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: <{msg_id}>\r\n"
        f"Date: Tue, 17 Jun 2026 12:00:00 +0000\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{body}"
    ).encode()


def test_maps_subject_sender_and_message_id() -> None:
    raw = _rfc822("Suspicious login from 1.2.3.4", "soc@example.test", "ABC-123@host", "Body.")
    p = _msg_to_payload(raw, "ci-mailbox")
    assert p is not None
    assert p.type == "imap.email"
    assert p.source == "ci-mailbox"
    assert p.source_ref == "ABC-123@host"
    assert p.title == "Suspicious login from 1.2.3.4"
    assert "Body." in (p.description or "")
    assert p.custom_fields["sender"] == "soc@example.test"
    assert any(t.startswith("sender:") for t in p.tags)


def test_drops_messages_without_message_id() -> None:
    raw = b"From: a@b\r\nSubject: x\r\nDate: Tue, 17 Jun 2026 12:00:00 +0000\r\n\r\nbody"
    assert _msg_to_payload(raw, "m") is None


def test_truncates_long_bodies() -> None:
    big = "X" * 20_000
    raw = _rfc822("t", "x@y", "M@h", big)
    p = _msg_to_payload(raw, "m")
    assert p is not None
    assert p.description is not None
    assert len(p.description) <= 8192
