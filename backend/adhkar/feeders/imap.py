"""IMAP feeder: pulls unread messages from a mailbox and yields one
AlertPayload per message.

Designed for SOC inboxes that receive forwarded phishing reports, vendor
alerts, etc. Uses `aioimaplib` if available; falls back to imaplib in a
thread for environments without the optional dep.

The mapping is deliberately conservative — we don't try to parse MIME
attachments or pull URLs from the body; that's the runner's job. Body
is truncated to 8 KiB to keep the alert row reasonable."""

from __future__ import annotations

import email
import email.policy
import email.utils
import imaplib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage

from adhkar.feeders.base import AlertPayload, Feeder

_BODY_LIMIT = 8192


@dataclass(frozen=True, slots=True)
class ImapFeederConfig:
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    mailbox: str = "INBOX"
    mark_as_seen: bool = True
    instance_name: str = "imap"


def _msg_to_payload(raw: bytes, instance: str) -> AlertPayload | None:
    msg: EmailMessage = email.message_from_bytes(raw, policy=email.policy.default)
    msg_id = msg["Message-ID"]
    if not msg_id:
        return None
    subject = str(msg["Subject"] or "(no subject)")
    sender = str(msg["From"] or "")
    body_text = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    body_text = part.get_content()
                except (LookupError, UnicodeDecodeError):
                    body_text = ""
                break
    else:
        try:
            body_text = msg.get_content()
        except (LookupError, UnicodeDecodeError):
            body_text = ""
    body_text = (body_text or "")[:_BODY_LIMIT]
    received_at_str = str(msg["Date"] or "")
    try:
        received_at = (
            email.utils.parsedate_to_datetime(received_at_str) if received_at_str else None
        )
    except (TypeError, ValueError):
        received_at = None
    return AlertPayload(
        type="imap.email",
        source=instance,
        source_ref=str(msg_id).strip("<>"),
        title=subject[:500],
        description=body_text,
        severity=2,
        tlp="amber",
        pap="amber",
        date=received_at or datetime.now(tz=UTC),
        tags=[f"sender:{sender}"] if sender else [],
        custom_fields={"sender": sender, "subject": subject},
        raw_payload={"headers": {k: str(v) for k, v in msg.items()}},
    )


class ImapFeeder(Feeder):
    name = "imap.mailbox.v1"
    description = "IMAP inbox poll — yields one alert per unread message."

    def __init__(self, config: ImapFeederConfig) -> None:
        self.config = config

    async def poll(self) -> AsyncIterator[AlertPayload]:
        import asyncio

        cfg = self.config

        def _drain() -> list[AlertPayload]:
            cls = imaplib.IMAP4_SSL if cfg.use_ssl else imaplib.IMAP4
            with cls(cfg.host, cfg.port) as imap:
                imap.login(cfg.username, cfg.password)
                imap.select(cfg.mailbox)
                status, data = imap.search(None, "UNSEEN")
                if status != "OK" or not data or not data[0]:
                    return []
                ids = data[0].split()
                out: list[AlertPayload] = []
                for msg_id in ids:
                    fetch_status, fetch_data = imap.fetch(msg_id, "(RFC822)")
                    if fetch_status != "OK" or not fetch_data:
                        continue
                    for tup in fetch_data:
                        if not isinstance(tup, tuple) or len(tup) < 2:
                            continue
                        raw = tup[1]
                        if not isinstance(raw, (bytes, bytearray)):
                            continue
                        payload = _msg_to_payload(bytes(raw), cfg.instance_name)
                        if payload is not None:
                            out.append(payload)
                    if cfg.mark_as_seen:
                        imap.store(msg_id, "+FLAGS", "\\Seen")
                imap.logout()
                return out

        payloads = await asyncio.to_thread(_drain)
        for p in payloads:
            yield p
