"""Mock CRM endpoint behaviour. Uses FastAPI TestClient — no network."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Disable fault injection for these tests so we exercise the happy + idempotency paths
# deterministically. Other tests cover retry behaviour against real fault injection.
os.environ.setdefault("CRM_FAULT_RATE_429", "0")
os.environ.setdefault("CRM_FAULT_RATE_503", "0")
os.environ.setdefault("CRM_LATENCY_MS_MIN", "0")
os.environ.setdefault("CRM_LATENCY_MS_MAX", "0")

from mock_crm import server as crm_server


@pytest.fixture
def client() -> TestClient:
    # Reset in-memory state between tests.
    crm_server._by_key.clear()
    crm_server._by_record.clear()
    crm_server._seq = 0
    # Force-disable fault injection at runtime (env may be cached in module-level vars).
    crm_server.FAULT_RATE_429 = 0.0
    crm_server.FAULT_RATE_503 = 0.0
    crm_server.LATENCY_MAX_MS = 0
    return TestClient(crm_server.app)


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestUpsert:
    def _body(self, **overrides: object) -> dict[str, object]:
        body = {
            "customer_id": "cust-1",
            "email": "a@b.example",
            "name": "Test",
            "dedup_key": "k0001",
        }
        body.update(overrides)
        return body

    def test_create_new_record(self, client: TestClient) -> None:
        body = self._body()
        r = client.post(
            "/v0/customer.upsert",
            json=body,
            headers={"Idempotency-Key": "key-1"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "created"
        assert data["customer_id"] == "cust-1"
        assert data["crm_record_id"].startswith("crm-")

    def test_replay_with_same_idempotency_key_returns_duplicate(self, client: TestClient) -> None:
        body = self._body()
        first = client.post(
            "/v0/customer.upsert",
            json=body,
            headers={"Idempotency-Key": "key-2"},
        )
        second = client.post(
            "/v0/customer.upsert",
            json=body,
            headers={"Idempotency-Key": "key-2"},
        )
        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json()["status"] == "duplicate"
        assert second.json()["crm_record_id"] == first.json()["crm_record_id"]

    def test_missing_idempotency_key_rejected(self, client: TestClient) -> None:
        r = client.post("/v0/customer.upsert", json=self._body())
        assert r.status_code == 422

    def test_missing_required_fields_rejected(self, client: TestClient) -> None:
        r = client.post(
            "/v0/customer.upsert",
            json={"email": "a@b.example"},
            headers={"Idempotency-Key": "key-3"},
        )
        assert r.status_code == 422

    def test_admin_records_returns_inserted(self, client: TestClient) -> None:
        client.post(
            "/v0/customer.upsert",
            json=self._body(),
            headers={"Idempotency-Key": "key-4"},
        )
        r = client.get("/v0/admin/records")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert body["records"][0]["customer_id"] == "cust-1"
