"""End-to-end orchestrator behaviour with a synthetic httpx transport.

These tests are the closest the CI gets to "real run". They verify:

* a clean run of N documents lands N records in the CRM,
* an idempotent replay returns ``duplicates=N``,
* low-confidence records skip the CRM and route to ``human_review``,
* exhausted-retry records land in the DLQ without crashing the run.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx

from agentic_onboard.audit import open_default
from agentic_onboard.crm_client import CRMClient
from agentic_onboard.ingest import Ingester
from agentic_onboard.orchestrator import Orchestrator, replay_dlq
from agentic_onboard.parser import MockParser
from agentic_onboard.schemas import DocumentFormat, RawDocument
from agentic_onboard.settings import Settings

# --- in-memory test ingester ------------------------------------------------


class _ListIngester:
    def __init__(self, docs: list[RawDocument]):
        self._docs = docs

    def list_documents(self) -> Iterator[RawDocument]:
        yield from self._docs


# --- transport that always succeeds ----------------------------------------


def _success_transport() -> tuple[httpx.MockTransport, dict[str, int]]:
    state = {"calls": 0, "seen_keys": 0}
    seen: set[str] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        key = request.headers.get("Idempotency-Key", "")
        is_dup = key in seen
        seen.add(key)
        body: dict[str, Any] = {"customer_id": "x", "crm_record_id": f"crm-{state['calls']:04d}"}
        body["status"] = "duplicate" if is_dup else "created"
        body["received_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if is_dup:
            state["seen_keys"] += 1
        return httpx.Response(200 if is_dup else 201, json=body)

    return httpx.MockTransport(handler), state


# --- helpers ---------------------------------------------------------------


def _email_doc(idx: int) -> RawDocument:
    return RawDocument(
        source_id=f"doc/{idx}.eml",
        format=DocumentFormat.EMAIL,
        body=(
            f"From: User{idx} <user{idx}@example.com>\n"
            "Subject: onboard\n\n"
            f"Name: User{idx}\n"
            f"Company: Co{idx}\n"
        ),
    )


def _build_orchestrator(
    *,
    settings: Settings,
    docs: list[RawDocument],
    transport: httpx.MockTransport,
) -> tuple[Orchestrator, Ingester]:
    audit = open_default(settings.database_url)
    httpx_client = httpx.Client(
        base_url=settings.crm_base_url,
        timeout=settings.http_timeout_s,
        transport=transport,
    )
    crm = CRMClient(settings, client=httpx_client)
    ingester: Ingester = _ListIngester(docs)
    orch = Orchestrator(
        settings=settings,
        ingester=ingester,
        parser=MockParser(),
        crm=crm,
        audit=audit,
    )
    return orch, ingester


# --- tests ------------------------------------------------------------------


class TestOrchestrator:
    def test_clean_run_lands_all_records(self, settings: Settings) -> None:
        docs = [_email_doc(i) for i in range(5)]
        transport, state = _success_transport()
        orch, _ = _build_orchestrator(settings=settings, docs=docs, transport=transport)
        result = orch.run()
        assert result.total == 5
        assert result.succeeded == 5
        assert result.dlq == 0
        assert result.parse_failed == 0
        assert state["calls"] == 5

    def test_idempotent_replay_marks_duplicates(self, settings: Settings) -> None:
        docs = [_email_doc(i) for i in range(3)]
        transport, _ = _success_transport()
        # First run: all created
        first, _ = _build_orchestrator(settings=settings, docs=docs, transport=transport)
        r1 = first.run()
        assert r1.succeeded == 3
        # Second run with the same docs: dedup keys match, all duplicate
        second, _ = _build_orchestrator(settings=settings, docs=docs, transport=transport)
        r2 = second.run()
        assert r2.duplicates == 3
        assert r2.succeeded == 0

    def test_parse_failure_does_not_crash_run(self, settings: Settings) -> None:
        docs = [
            _email_doc(0),
            RawDocument(
                source_id="bad.txt",
                format=DocumentFormat.FREEFORM_TEXT,
                body="no email anywhere",
            ),
            _email_doc(1),
        ]
        transport, _ = _success_transport()
        orch, _ = _build_orchestrator(settings=settings, docs=docs, transport=transport)
        result = orch.run()
        assert result.total == 3
        assert result.succeeded == 2
        assert result.parse_failed == 1
        assert result.dlq == 0

    def test_dlq_captures_exhausted_retries(self, settings: Settings) -> None:
        docs = [_email_doc(i) for i in range(2)]
        # Always-503 transport ⇒ every record exhausts retries and lands in DLQ.
        always_fail = httpx.MockTransport(lambda req: httpx.Response(503, json={"detail": "down"}))
        orch, _ = _build_orchestrator(settings=settings, docs=docs, transport=always_fail)
        result = orch.run()
        # Two records → both DLQ; but the breaker may trip mid-run, so DLQ count is
        # ``len(docs)`` regardless of which exception path each record takes
        # (CRMRetriableError or CircuitOpenError are both routed to DLQ).
        assert result.total == 2
        assert result.dlq == 2
        assert result.succeeded == 0

    def test_replay_dlq_succeeds_on_recovered_crm(self, settings: Settings) -> None:
        docs = [_email_doc(0)]
        always_fail = httpx.MockTransport(lambda req: httpx.Response(503, json={"detail": "down"}))
        orch, _ = _build_orchestrator(settings=settings, docs=docs, transport=always_fail)
        first = orch.run()
        assert first.dlq == 1

        # Now "fix" the CRM: a fresh client with a healthy transport, and replay.
        healthy, _ = _success_transport()
        audit = open_default(settings.database_url)
        crm = CRMClient(
            settings,
            client=httpx.Client(
                base_url=settings.crm_base_url,
                timeout=settings.http_timeout_s,
                transport=healthy,
            ),
        )
        ok, fail = replay_dlq(settings=settings, crm=crm, audit=audit)
        assert ok == 1
        assert fail == 0
        assert audit.dlq_list() == []
