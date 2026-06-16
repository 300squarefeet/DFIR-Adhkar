"""Lightweight SMTP sender (dev → MailHog; prod → real SMTP)."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from adhkar.core.settings import Settings

_log = logging.getLogger(__name__)


def _send_sync(settings: Settings, to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as s:
        s.send_message(msg)


async def send_email(settings: Settings, *, to: str, subject: str, body: str) -> None:
    try:
        await asyncio.to_thread(_send_sync, settings, to, subject, body)
        _log.info("email sent", extra={"to": to, "subject": subject})
    except Exception:
        _log.exception("email send failed", extra={"to": to, "subject": subject})
