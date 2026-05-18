"""Shared pytest fixtures.

Every test gets a fresh ``Settings`` (no .env leakage), a fresh sqlite-backed
``AuditStore`` in tmp_path (no global DB), and an in-memory mock CRM bound to
an httpx.MockTransport (no real network).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from agentic_onboard.audit import AuditStore
from agentic_onboard.crm_client import CRMClient
from agentic_onboard.parser import MockParser
from agentic_onboard.settings import Settings

# --- Settings: never read .env in tests ---


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Hermetic Settings — points the audit DB at tmp_path, mock LLM, fast retries."""
    return Settings(
        llm_provider="mock",
        crm_base_url="http://test.local",
        retry_max_attempts=3,
        retry_initial_backoff_s=0.01,
        retry_max_backoff_s=0.05,
        circuit_breaker_threshold=3,
        circuit_breaker_reset_s=0.2,
        database_url=f"sqlite:///{tmp_path / 'audit.db'}",
        log_level="WARNING",
        http_timeout_s=2.0,
    )


# --- AuditStore ---


@pytest.fixture
def audit(settings: Settings) -> Iterator[AuditStore]:
    """Per-test AuditStore. Closed at teardown."""
    from agentic_onboard.audit import open_default

    store = open_default(settings.database_url)
    try:
        yield store
    finally:
        store.close()


# --- Parser ---


@pytest.fixture
def parser() -> MockParser:
    return MockParser()


# --- httpx.MockTransport CRM helpers ---


def make_crm_client(
    *,
    settings: Settings,
    handler: httpx.MockTransport,
) -> CRMClient:
    """CRMClient bound to a synthetic httpx transport (no real sockets)."""
    client = httpx.Client(
        base_url=settings.crm_base_url,
        timeout=settings.http_timeout_s,
        transport=handler,
    )
    return CRMClient(settings, client=client)
