"""Secret redaction tests — make sure API keys never leak through structured logs.

These tests are the contract behind the README's security claim. Adding a new
secret format? Add it to ``_SECRET_PATTERNS`` and add a test row here.
"""

from __future__ import annotations

import pytest

from agentic_onboard.logging_config import _redact, _redact_event


@pytest.mark.parametrize(
    ("raw", "should_be_redacted"),
    [
        ("sk-or-v1-abcdefghijklmnopqrstuvwxyz", True),
        ("sk-or-v2-aaaaaaaaaaaaaaaaaaaa1234", True),
        ("sk-proj-1234567890abcdefghij1234", True),
        ("sk-1234567890abcdefghijklmnopqr", True),
        ("sk-ant-api03-abcdefghijklmnopqrstuv", True),
        ("Bearer ABCDEFGHIJKLMNOP1234567890", True),
        ("token abcdefghijklmnop1234", True),
        ("just a normal string with no secret", False),
        ("AKIAIOSFODNN7EXAMPLE", False),  # AWS keys are out of scope here
    ],
)
def test_redact_string(raw: str, should_be_redacted: bool) -> None:
    out = _redact(raw)
    if should_be_redacted:
        assert "***REDACTED***" in out
        # No 16+ char run of token-shaped chars should remain.
        # (loose check; full exhaustiveness is the patterns themselves)
        assert raw not in out
    else:
        assert out == raw


def test_redact_event_walks_dict() -> None:
    event = {
        "msg": "auth header sent: Bearer ABCDEFGHIJKLMNOP1234",
        "headers": {
            "Authorization": "Bearer ZZZYYYXXXWWWVVVUUUTT1122",
            "X-Other": "fine",
        },
        "stack": ["sk-or-v1-leak0123456789abcdef"],
        "count": 7,
    }
    out = _redact_event(None, "info", event)
    assert "Bearer ABCDEFGHIJKLMNOP1234" not in str(out)
    assert "sk-or-v1-leak0123456789abcdef" not in str(out)
    assert out["headers"]["X-Other"] == "fine"  # untouched
    assert out["count"] == 7  # non-strings untouched


def test_redact_handles_jwt_shape() -> None:
    jwt = (
        "eyJhbGciOiJIUzI1NiJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    out = _redact(f"token={jwt}")
    assert "***REDACTED***" in out
    assert jwt not in out
