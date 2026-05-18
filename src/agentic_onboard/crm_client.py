"""Resilient client for the legacy CRM.

Layers, outermost first:

    1. Circuit breaker — fast-fails after N consecutive infra-level failures so
       we don't pile up retries against a downed service.
    2. Tenacity retry policy — exponential backoff with jitter, *only* on
       retriable errors (429 + 5xx + connection errors). 4xx other than 429
       is a programming bug, not a transient: it bubbles up immediately.
    3. Idempotency key — every request carries a sha256 ``Idempotency-Key``
       header. If the CRM has already seen the key, it returns
       ``status="duplicate"`` instead of mutating again.
    4. The actual HTTP call (httpx).

The client is instantiated once per run by the orchestrator. It owns a
single httpx.Client (connection pooling) and a single CircuitBreaker
(shared state across calls).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .circuit_breaker import CircuitBreaker, CircuitOpenError
from .logging_config import get_logger
from .schemas import CRMUpsertRequest, CRMUpsertResponse
from .settings import Settings

if TYPE_CHECKING:
    from types import TracebackType

# Re-export for callers that catch breaker errors at the orchestrator boundary.
__all__ = [
    "CRMClient",
    "CRMError",
    "CRMPermanentError",
    "CRMRetriableError",
    "CircuitOpenError",
]

log = get_logger(__name__)


class CRMError(Exception):
    """Base class for CRM client errors that callers (the orchestrator) handle."""


class CRMRetriableError(CRMError):
    """Transient — retried by tenacity (429, 502, 503, 504, network)."""


class CRMPermanentError(CRMError):
    """Non-retriable (4xx other than 429). Surfaces immediately to the caller."""


# Status codes we will retry. Tenacity retries on `CRMRetriableError`; we
# raise that for these codes. Everything else 4xx is a permanent failure.
_RETRIABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class CRMClient:
    """Idempotent, retrying, circuit-breaker-guarded client for the legacy CRM.

    Use as a context manager so the underlying httpx.Client is closed cleanly:

        with CRMClient(settings) as crm:
            resp = crm.upsert(request)
    """

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        self._settings = settings
        self._client = client or httpx.Client(
            base_url=settings.crm_base_url,
            timeout=settings.http_timeout_s,
            headers={"User-Agent": "agentic-onboard/0.1.0"},
        )
        self._owns_client = client is None
        self._breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_threshold,
            reset_after_s=settings.circuit_breaker_reset_s,
            name="crm",
        )

    # --- context manager ---

    def __enter__(self) -> CRMClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Release the underlying httpx connection pool."""
        if self._owns_client:
            self._client.close()

    # --- introspection (orchestrator queries this for the audit log) ---

    @property
    def breaker(self) -> CircuitBreaker:
        return self._breaker

    # --- public API ---

    def upsert(self, request: CRMUpsertRequest) -> CRMUpsertResponse:
        """Send the request, retrying transients and short-circuiting if open.

        Returns:
            ``CRMUpsertResponse`` on success.

        Raises:
            CircuitOpenError: breaker tripped — request never sent. Caller
                should DLQ the record and back off.
            CRMRetriableError: every retry exhausted — caller should DLQ.
            CRMPermanentError: 4xx response (other than 429). Caller should
                send to human review or treat as a parser bug.
        """
        # Layer 1: breaker — never even open the socket if the CRM is hosed.
        self._breaker.before_call()

        # Layer 2: tenacity. We drive ``Retrying`` manually with the
        # ``for attempt in retryer`` loop so we can read ``retry_state``
        # for clean log lines without coupling the inner function to it.
        retryer = Retrying(
            stop=stop_after_attempt(self._settings.retry_max_attempts),
            wait=wait_exponential_jitter(
                initial=self._settings.retry_initial_backoff_s,
                max=self._settings.retry_max_backoff_s,
                jitter=self._settings.retry_initial_backoff_s,
            ),
            retry=retry_if_exception_type(CRMRetriableError),
            reraise=True,
        )

        response: CRMUpsertResponse | None = None
        try:
            for attempt in retryer:
                with attempt:
                    response = self._do_upsert(
                        request,
                        attempt_number=attempt.retry_state.attempt_number,
                    )
        except CRMRetriableError:
            self._breaker.record_failure()
            raise
        except CRMPermanentError:
            # Permanent errors are not the CRM's fault per se — don't trip the
            # breaker. Bubble up so the orchestrator can route the record.
            raise

        # ``response`` is set on the final successful iteration; assert for mypy.
        assert response is not None
        self._breaker.record_success()
        return response

    # --- internals ---

    def _do_upsert(self, request: CRMUpsertRequest, *, attempt_number: int) -> CRMUpsertResponse:
        """One HTTP attempt. Translates status codes into typed errors.

        Returns the parsed response on 200/201; raises ``CRMRetriableError``
        on 429/5xx and on connection errors; raises ``CRMPermanentError`` on
        any other 4xx so the caller sees the misuse signal.
        """
        log.debug(
            "crm.attempt",
            customer_id=request.customer_id,
            attempt=attempt_number,
        )
        try:
            response = self._client.post(
                "/v0/customer.upsert",
                json=request.model_dump(mode="json"),
                headers={"Idempotency-Key": request.dedup_key},
            )
        except httpx.HTTPError as exc:
            # Connection refused, DNS, timeout, read error — all transient.
            raise CRMRetriableError(f"connection-level error: {exc}") from exc

        if response.status_code in (200, 201):
            return CRMUpsertResponse.model_validate(response.json())

        if response.status_code in _RETRIABLE_STATUS:
            log.info(
                "crm.retriable",
                customer_id=request.customer_id,
                status=response.status_code,
                attempt=attempt_number,
            )
            raise CRMRetriableError(
                f"CRM returned {response.status_code} (attempt {attempt_number}): "
                f"{response.text[:200]}"
            )

        # Anything else (400, 401, 403, 404, 422, …) is a programmer / data bug.
        raise CRMPermanentError(f"CRM returned {response.status_code}: {response.text[:200]}")
