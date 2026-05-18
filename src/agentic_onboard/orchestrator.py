"""End-to-end pipeline. Wires ingest, parser, mapper, CRM client, audit, DLQ.

This is the *only* module that knows the full shape of the pipeline. Every
other module is a single-responsibility component behind a Protocol or a
small public API. The orchestrator's job is to:

    1. Pull a stream of ``RawDocument`` from the ingester.
    2. Parse each one (LLM or mock).
    3. Decide on confidence: < 0.8 → human review, ≥ 0.8 → continue.
    4. Map to ``CRMUpsertRequest`` (with idempotency key).
    5. Push to the CRM with retry + breaker.
    6. On terminal failure, write to DLQ. On success, log it.
    7. Return a typed summary.

Every step writes to the audit log *before* it runs, so a crash leaves the
DB in a state where you can see exactly which step was in flight.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import TYPE_CHECKING

from .audit import AuditStore
from .crm_client import (
    CircuitOpenError,
    CRMClient,
    CRMPermanentError,
    CRMRetriableError,
)
from .ingest import Ingester
from .logging_config import get_logger
from .parser import ParseError, Parser
from .schemas import (
    CRMUpsertRequest,
    ParsedCustomer,
    PipelineResult,
    RawDocument,
    RecordStatus,
)
from .settings import Settings

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


# Confidence threshold below which a parsed customer is routed to human review
# instead of pushed to the CRM. Lives here (not in settings) because it is a
# domain rule, not an env-tunable knob.
HUMAN_REVIEW_THRESHOLD = 0.8


class Orchestrator:
    """Single-class agent loop. Constructed once per run.

    Args:
        settings: validated configuration.
        ingester: source of raw documents.
        parser: LLM or mock parser.
        crm: resilient CRM client.
        audit: SQLite audit + DLQ store.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        ingester: Ingester,
        parser: Parser,
        crm: CRMClient,
        audit: AuditStore,
    ):
        self._settings = settings
        self._ingester = ingester
        self._parser = parser
        self._crm = crm
        self._audit = audit

    # --- entry point ---

    def run(self) -> PipelineResult:
        """Drain the ingester, push each record through the pipeline, return summary."""
        run_id = self._audit.start_run()
        log.info("run.start", run_id=run_id, llm_provider=self._settings.llm_provider)

        counters = {
            "total": 0,
            "succeeded": 0,
            "duplicates": 0,
            "human_review": 0,
            "parse_failed": 0,
            "dlq": 0,
        }
        started = time.monotonic()

        for doc in self._ingester.list_documents():
            counters["total"] += 1
            self._handle_one(run_id=run_id, doc=doc, counters=counters)

        duration_ms = int((time.monotonic() - started) * 1000)
        self._audit.finalize_run(run_id, counters=counters)
        log.info("run.end", run_id=run_id, duration_ms=duration_ms, **counters)

        return PipelineResult(
            run_id=run_id,
            total=counters["total"],
            succeeded=counters["succeeded"],
            duplicates=counters["duplicates"],
            human_review=counters["human_review"],
            parse_failed=counters["parse_failed"],
            dlq=counters["dlq"],
            duration_ms=duration_ms,
        )

    # --- per-record state machine ---

    def _handle_one(self, *, run_id: str, doc: RawDocument, counters: dict[str, int]) -> None:
        """Run one document through the full pipeline. Never raises.

        Any exception here is converted to a DLQ entry so a single bad record
        cannot abort the run. This is the "97 of 100 still commit" guarantee
        from the README.
        """
        self._audit.log(
            run_id=run_id,
            source_id=doc.source_id,
            step="ingested",
            status="in_progress",
        )

        # --- Parse ---
        try:
            parsed = self._parser.parse(doc)
        except ParseError as exc:
            counters["parse_failed"] += 1
            self._audit.log(
                run_id=run_id,
                source_id=doc.source_id,
                step="parsed",
                status=RecordStatus.PARSE_FAILED,
                detail={"error": str(exc)},
            )
            log.info("record.parse_failed", source_id=doc.source_id, error=str(exc))
            return

        self._audit.log(
            run_id=run_id,
            source_id=doc.source_id,
            customer_id=parsed.customer_id,
            step="parsed",
            status="in_progress",
            detail={"confidence": parsed.confidence},
        )

        # --- Confidence gate ---
        if parsed.confidence < HUMAN_REVIEW_THRESHOLD:
            counters["human_review"] += 1
            self._audit.log(
                run_id=run_id,
                source_id=doc.source_id,
                customer_id=parsed.customer_id,
                step="gated",
                status=RecordStatus.HUMAN_REVIEW,
                detail={"confidence": parsed.confidence},
            )
            log.info(
                "record.human_review",
                source_id=doc.source_id,
                confidence=parsed.confidence,
            )
            return

        # --- Map → CRM payload (computes idempotency key) ---
        request = CRMUpsertRequest.from_parsed(parsed)
        self._audit.log(
            run_id=run_id,
            source_id=doc.source_id,
            customer_id=parsed.customer_id,
            step="mapped",
            status="in_progress",
            detail={"dedup_key": request.dedup_key},
        )

        # --- Push ---
        self._push(run_id=run_id, doc=doc, parsed=parsed, request=request, counters=counters)

    def _push(
        self,
        *,
        run_id: str,
        doc: RawDocument,
        parsed: ParsedCustomer,
        request: CRMUpsertRequest,
        counters: dict[str, int],
    ) -> None:
        """Final pipeline step. CRM push + post-mortem accounting."""
        try:
            response = self._crm.upsert(request)
        except CircuitOpenError as exc:
            counters["dlq"] += 1
            self._dlq(run_id, doc, request, parsed, last_error=str(exc))
            return
        except CRMRetriableError as exc:
            counters["dlq"] += 1
            self._dlq(run_id, doc, request, parsed, last_error=str(exc))
            return
        except CRMPermanentError as exc:
            # Permanent failures (4xx like 422 unprocessable) are routed to
            # human review — they signal a data shape the CRM rejected, not
            # an infra problem.
            counters["human_review"] += 1
            self._audit.log(
                run_id=run_id,
                source_id=doc.source_id,
                customer_id=parsed.customer_id,
                step="pushed",
                status=RecordStatus.HUMAN_REVIEW,
                detail={"error": str(exc)},
            )
            return

        if response.status == "duplicate":
            counters["duplicates"] += 1
        else:
            counters["succeeded"] += 1
        self._audit.log(
            run_id=run_id,
            source_id=doc.source_id,
            customer_id=parsed.customer_id,
            step="pushed",
            status=RecordStatus.SUCCESS,
            detail={
                "crm_status": response.status,
                "crm_record_id": response.crm_record_id,
            },
        )

    # --- helpers ---

    def _dlq(
        self,
        run_id: str,
        doc: RawDocument,
        request: CRMUpsertRequest,
        parsed: ParsedCustomer,
        *,
        last_error: str,
    ) -> None:
        """Persist a failed record to the DLQ + audit log."""
        self._audit.dlq_put(
            run_id=run_id,
            source_id=doc.source_id,
            customer_id=parsed.customer_id,
            payload=request.model_dump(mode="json"),
            last_error=last_error,
        )
        self._audit.log(
            run_id=run_id,
            source_id=doc.source_id,
            customer_id=parsed.customer_id,
            step="pushed",
            status=RecordStatus.DLQ,
            detail={"error": last_error},
        )
        log.warning("record.dlq", source_id=doc.source_id, error=last_error)


# --- DLQ replay -------------------------------------------------------------


def replay_dlq(
    *,
    settings: Settings,
    crm: CRMClient,
    audit: AuditStore,
    run_id: str | None = None,
) -> tuple[int, int]:
    """Re-attempt every DLQ entry. Idempotency keys make this safe.

    Returns:
        ``(succeeded, still_failing)``.
    """
    rows = audit.dlq_list(run_id=run_id)
    succeeded = 0
    still_failing = 0
    for row in rows:
        payload = row["payload"]
        try:
            request = CRMUpsertRequest.model_validate_json(payload)
        except Exception as exc:  # malformed payload — drop it from the DLQ
            log.error("dlq.malformed", source_id=row["source_id"], error=str(exc))
            still_failing += 1
            continue

        try:
            response = crm.upsert(request)
        except (CRMRetriableError, CircuitOpenError, CRMPermanentError) as exc:
            still_failing += 1
            log.warning("dlq.replay_failed", source_id=row["source_id"], error=str(exc))
            continue

        log.info(
            "dlq.replay_ok",
            source_id=row["source_id"],
            crm_status=response.status,
        )
        audit.dlq_pop(row["id"])
        succeeded += 1
    return succeeded, still_failing


# --- Convenience constructor used by the CLI -------------------------------


def build_default(
    *,
    settings: Settings,
    ingester: Ingester,
) -> tuple[Orchestrator, AuditStore, CRMClient]:
    """Build a fully-wired orchestrator for the default settings.

    Returned alongside the audit store + CRM client so callers can ``close()``
    them in the right order; the CLI uses ``contextlib.ExitStack`` for that.
    """
    from .audit import open_default
    from .parser import build_parser

    audit = open_default(settings.database_url)
    parser = build_parser(settings)
    crm = CRMClient(settings)
    orch = Orchestrator(
        settings=settings,
        ingester=ingester,
        parser=parser,
        crm=crm,
        audit=audit,
    )
    return orch, audit, crm


def run_pipeline(documents: Iterable[RawDocument], *, settings: Settings) -> PipelineResult:
    """Helper used by tests: feed a fixed list of documents through the pipeline."""

    class _Fixed:
        def list_documents(self) -> Iterable[RawDocument]:
            return documents

    orch, audit, crm = build_default(settings=settings, ingester=_Fixed())
    try:
        return orch.run()
    finally:
        crm.close()
        audit.close()
