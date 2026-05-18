"""CRMClient resilience: retry, idempotency-key, circuit breaker, error mapping."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from agentic_onboard.crm_client import (
    CircuitOpenError,
    CRMPermanentError,
    CRMRetriableError,
)
from agentic_onboard.schemas import CRMUpsertRequest, ParsedCustomer
from agentic_onboard.settings import Settings

from .conftest import make_crm_client

# --- helpers ----------------------------------------------------------------


def _request() -> CRMUpsertRequest:
    parsed = ParsedCustomer(
        source_id="t/1",
        customer_id="cust-99",
        name="Test User",
        email="t@example.com",
        confidence=0.95,
    )
    return CRMUpsertRequest.from_parsed(parsed)


def _success_payload(req: CRMUpsertRequest) -> dict[str, Any]:
    return {
        "customer_id": req.customer_id,
        "status": "created",
        "crm_record_id": "crm-000001",
        "received_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


# --- tests ------------------------------------------------------------------


class TestCRMClient:
    def test_happy_path_201(self, settings: Settings) -> None:
        req = _request()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Idempotency-Key"] == req.dedup_key
            assert request.url.path == "/v0/customer.upsert"
            return httpx.Response(201, json=_success_payload(req))

        client = make_crm_client(settings=settings, handler=httpx.MockTransport(handler))
        with client as crm:
            resp = crm.upsert(req)
        assert resp.status == "created"
        assert resp.crm_record_id == "crm-000001"

    def test_retries_429_then_succeeds(self, settings: Settings) -> None:
        req = _request()
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(429, json={"detail": "rate limit"})
            return httpx.Response(201, json=_success_payload(req))

        client = make_crm_client(settings=settings, handler=httpx.MockTransport(handler))
        with client as crm:
            resp = crm.upsert(req)
        assert resp.status == "created"
        assert calls["n"] == 3  # two retries + success

    def test_retries_503_then_succeeds(self, settings: Settings) -> None:
        req = _request()
        calls = {"n": 0}

        def handler(_: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(503, json={"detail": "down"})
            return httpx.Response(201, json=_success_payload(req))

        client = make_crm_client(settings=settings, handler=httpx.MockTransport(handler))
        with client as crm:
            resp = crm.upsert(req)
        assert resp.status == "created"
        assert calls["n"] == 2

    def test_exhausts_retries_then_raises(self, settings: Settings) -> None:
        req = _request()

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "down"})

        client = make_crm_client(settings=settings, handler=httpx.MockTransport(handler))
        with client as crm, pytest.raises(CRMRetriableError):
            crm.upsert(req)

    def test_4xx_other_than_429_is_permanent(self, settings: Settings) -> None:
        req = _request()

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"detail": "schema invalid"})

        client = make_crm_client(settings=settings, handler=httpx.MockTransport(handler))
        with client as crm, pytest.raises(CRMPermanentError):
            crm.upsert(req)

    def test_breaker_opens_after_repeated_failures(self, settings: Settings) -> None:
        """After the breaker threshold of consecutive failed CRM calls, a
        subsequent call should fast-fail with ``CircuitOpenError`` and never
        even hit the transport."""
        req = _request()
        calls = {"n": 0}

        def handler(_: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503, json={"detail": "down"})

        client = make_crm_client(settings=settings, handler=httpx.MockTransport(handler))
        with client as crm:
            # Each upsert eats `retry_max_attempts`=3 calls and then bumps the
            # breaker by 1. settings.circuit_breaker_threshold == 3, so we
            # need 3 failed upserts to trip it.
            for _ in range(3):
                with pytest.raises(CRMRetriableError):
                    crm.upsert(req)

            # The breaker is now OPEN — the next call must fast-fail.
            calls_before = calls["n"]
            with pytest.raises(CircuitOpenError):
                crm.upsert(req)
            assert calls["n"] == calls_before  # no socket touched

    def test_idempotency_header_carries_dedup_key(self, settings: Settings) -> None:
        req = _request()
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["key"] = request.headers["Idempotency-Key"]
            captured["body"] = request.content.decode()
            return httpx.Response(201, json=_success_payload(req))

        client = make_crm_client(settings=settings, handler=httpx.MockTransport(handler))
        with client as crm:
            crm.upsert(req)
        assert captured["key"] == req.dedup_key
        body = json.loads(captured["body"])
        assert body["dedup_key"] == req.dedup_key

    def test_connection_error_is_retriable(self, settings: Settings) -> None:
        req = _request()
        calls = {"n": 0}

        def handler(_: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ConnectError("simulated network drop")
            return httpx.Response(201, json=_success_payload(req))

        client = make_crm_client(settings=settings, handler=httpx.MockTransport(handler))
        with client as crm:
            resp = crm.upsert(req)
        assert resp.status == "created"
        assert calls["n"] == 2
