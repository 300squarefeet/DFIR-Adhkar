"""structlog-based JSON logging configured from Settings."""

import logging
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import structlog

from adhkar.core.settings import Settings

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _REQUEST_ID.get()


def set_request_id(rid: str) -> None:
    _REQUEST_ID.set(rid)


def _add_request_id(
    _logger: object,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    event_dict.setdefault("request_id", _REQUEST_ID.get())
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure stdlib + structlog to emit JSON lines on stdout."""

    level = logging.getLevelName(settings.log_level)
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s", force=True)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            _add_request_id,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
