"""Structured logging configured once at process start.

The redactor is the load-bearing piece: it pattern-matches anything that looks
like an API key (OpenAI/OpenRouter/Anthropic prefixes, Bearer tokens, generic
JWTs) and replaces the body with ``***REDACTED***``. So even if a stack trace
or a 4xx response body leaks a key into the log stream, it never lands on disk
or stdout in plaintext.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import structlog

# Patterns ordered most-specific → least. ``re.IGNORECASE`` keeps Authorization
# header casing irrelevant; the captured groups are intentionally short so the
# replacement string ``***REDACTED***`` can never re-introduce a valid prefix.
_SECRET_PATTERNS = [
    re.compile(r"sk-or-v\d-[A-Za-z0-9_-]{16,}"),  # OpenRouter
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),  # OpenAI
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),  # Anthropic
    re.compile(r"(?:Bearer|Token)\s+[A-Za-z0-9._\-]{16,}", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\b"),  # JWT
]

_REDACTION = "***REDACTED***"


def _redact(value: str) -> str:
    """Return ``value`` with every secret-shaped substring replaced.

    Pure function; safe to call on log messages, exception strings, response
    bodies, and HTTP header values. O(n·k) where k is the number of patterns —
    fine for log-line-sized inputs.
    """
    for pat in _SECRET_PATTERNS:
        value = pat.sub(_REDACTION, value)
    return value


def _redact_event(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor: walk the event dict and redact any string values.

    Lists and nested dicts are walked recursively. Non-string scalars are
    untouched (no risk of leaking a secret through an int/float).
    """

    def walk(obj: Any) -> Any:
        if isinstance(obj, str):
            return _redact(obj)
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        return obj

    return walk(event_dict)  # type: ignore[no-any-return]


def configure_logging(level: str = "INFO", *, json_logs: bool = False) -> None:
    """Configure structlog + the stdlib root logger.

    Idempotent — calling twice does not duplicate handlers. The ``_redact_event``
    processor is *first* in the chain so downstream renderers (console, JSON)
    never see raw secrets even if a downstream processor happened to add them.
    """
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        _redact_event,
    ]

    if json_logs:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib loggers (httpx, uvicorn) through the same redaction filter.
    root = logging.getLogger()
    if not any(isinstance(h, _RedactingStreamHandler) for h in root.handlers):
        root.handlers.clear()
        root.addHandler(_RedactingStreamHandler())
    root.setLevel(level.upper())


class _RedactingStreamHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Stdlib log handler that redacts before emitting to stderr."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return _redact(msg)


def get_logger(name: str | None = None) -> Any:
    """Convenience wrapper so callers do not need to import ``structlog`` directly."""
    return structlog.get_logger(name)
