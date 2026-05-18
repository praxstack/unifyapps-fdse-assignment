"""AuditStore: log, run lifecycle, DLQ upsert, replay."""

from __future__ import annotations

from agentic_onboard.audit import AuditStore
from agentic_onboard.schemas import RecordStatus


class TestRunLifecycle:
    def test_start_and_finalize_run(self, audit: AuditStore) -> None:
        run_id = audit.start_run()
        assert len(run_id) == 32  # uuid4 hex
        audit.finalize_run(
            run_id,
            counters={"total": 5, "succeeded": 4, "dlq": 1},
        )
        # finalize is idempotent — should not raise on re-call.
        audit.finalize_run(run_id, counters={"total": 5})


class TestAuditLog:
    def test_log_appends_row(self, audit: AuditStore) -> None:
        run_id = audit.start_run()
        audit.log(
            run_id=run_id,
            source_id="t/1.eml",
            step="ingested",
            status="in_progress",
            customer_id="cust-1",
            detail={"foo": "bar"},
        )
        rows = audit.list_audit(run_id)
        assert len(rows) == 1
        assert rows[0]["step"] == "ingested"
        assert rows[0]["customer_id"] == "cust-1"
        assert rows[0]["detail"] == '{"foo": "bar"}'

    def test_log_accepts_record_status_enum(self, audit: AuditStore) -> None:
        run_id = audit.start_run()
        audit.log(
            run_id=run_id,
            source_id="t/1.eml",
            step="parsed",
            status=RecordStatus.HUMAN_REVIEW,
        )
        rows = audit.list_audit(run_id)
        assert rows[0]["status"] == "human_review"

    def test_audit_log_ordered_by_id(self, audit: AuditStore) -> None:
        run_id = audit.start_run()
        for step in ["ingested", "parsed", "mapped", "pushed"]:
            audit.log(run_id=run_id, source_id="t/1", step=step, status="in_progress")
        rows = audit.list_audit(run_id)
        assert [r["step"] for r in rows] == ["ingested", "parsed", "mapped", "pushed"]


class TestDLQ:
    def test_put_inserts_row(self, audit: AuditStore) -> None:
        run_id = audit.start_run()
        audit.dlq_put(
            run_id=run_id,
            source_id="t/1",
            payload={"customer_id": "x", "email": "x@y.example"},
            last_error="boom",
            customer_id="cust-1",
        )
        rows = audit.dlq_list()
        assert len(rows) == 1
        assert rows[0]["last_error"] == "boom"
        assert rows[0]["attempt_count"] == 1

    def test_put_upserts_existing_run_source(self, audit: AuditStore) -> None:
        run_id = audit.start_run()
        for i in range(3):
            audit.dlq_put(
                run_id=run_id,
                source_id="t/1",
                payload={"x": i},
                last_error=f"err-{i}",
            )
        rows = audit.dlq_list(run_id=run_id)
        assert len(rows) == 1
        assert rows[0]["attempt_count"] == 3
        assert rows[0]["last_error"] == "err-2"

    def test_pop_removes_row(self, audit: AuditStore) -> None:
        run_id = audit.start_run()
        audit.dlq_put(run_id=run_id, source_id="t/1", payload={}, last_error="boom")
        rows = audit.dlq_list()
        audit.dlq_pop(rows[0]["id"])
        assert audit.dlq_list() == []

    def test_dlq_list_filtered_by_run(self, audit: AuditStore) -> None:
        run_a = audit.start_run()
        run_b = audit.start_run()
        audit.dlq_put(run_id=run_a, source_id="a/1", payload={}, last_error="a")
        audit.dlq_put(run_id=run_b, source_id="b/1", payload={}, last_error="b")
        assert len(audit.dlq_list(run_id=run_a)) == 1
        assert len(audit.dlq_list()) == 2
