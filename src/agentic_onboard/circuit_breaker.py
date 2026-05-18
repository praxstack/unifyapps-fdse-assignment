"""Hand-rolled circuit breaker — three states, fail-fast on open.

Why hand-rolled instead of a library: the pattern is twenty lines and a
``pybreaker`` dependency would obscure it. Reviewers (UnifyApps cares about
this) can see exactly how the breaker decides to trip and how it recovers.

State machine:

    CLOSED ── failure_count >= threshold ──> OPEN
    OPEN   ── reset_after seconds elapsed ──> HALF_OPEN
    HALF_OPEN ── success ──> CLOSED   (and zero the counter)
                ── failure ──> OPEN   (and reset the timer)

Thread-safety: a single ``threading.Lock`` guards all transitions. The
breaker is fast to acquire/release — no I/O happens inside the critical
section, just integer compare-and-set.
"""

from __future__ import annotations

import threading
import time
from enum import StrEnum

from .logging_config import get_logger

log = get_logger(__name__)


class State(StrEnum):
    """The three states of the breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a request is fast-failed because the breaker is open.

    The orchestrator catches this and routes the record to the DLQ, then
    waits ``reset_after`` seconds before resuming so the breaker has a
    chance to recover.
    """

    def __init__(self, *, retry_after_s: float):
        super().__init__(
            f"circuit breaker is open — request rejected, retry_after_s={retry_after_s:.1f}"
        )
        self.retry_after_s = retry_after_s


class CircuitBreaker:
    """Fail-fast guard around an unreliable downstream.

    Args:
        failure_threshold: consecutive failures before tripping the breaker open.
        reset_after_s: seconds the breaker stays open before a probe (HALF_OPEN).
        name: identifier used in log messages — useful when you have many breakers.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_after_s: float = 15.0,
        name: str = "default",
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if reset_after_s <= 0:
            raise ValueError("reset_after_s must be > 0")

        self._threshold = failure_threshold
        self._reset_after = reset_after_s
        self._name = name

        self._state: State = State.CLOSED
        self._failure_count: int = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    # --- introspection (used in tests + audit log) ---

    @property
    def state(self) -> State:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    # --- public API ---

    def before_call(self) -> None:
        """Raise :class:`CircuitOpenError` if the breaker is open.

        Call this immediately before the protected operation. After the call
        returns (success or failure), use :meth:`record_success` or
        :meth:`record_failure` to update the breaker state.
        """
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._state is State.OPEN:
                retry_after = self._seconds_until_half_open()
                raise CircuitOpenError(retry_after_s=retry_after)

    def record_success(self) -> None:
        """Mark the latest protected call as successful — closes a half-open breaker."""
        with self._lock:
            if self._state is State.HALF_OPEN:
                log.info("circuit_breaker.closed", name=self._name)
            self._state = State.CLOSED
            self._failure_count = 0
            self._opened_at = None

    def record_failure(self) -> None:
        """Mark the latest call as a failure — may trip the breaker open."""
        with self._lock:
            self._failure_count += 1
            if self._state is State.HALF_OPEN:
                # A failed probe re-opens immediately; restart the cooldown.
                self._state = State.OPEN
                self._opened_at = time.monotonic()
                log.warning("circuit_breaker.reopened", name=self._name)
                return

            if self._failure_count >= self._threshold and self._state is State.CLOSED:
                self._state = State.OPEN
                self._opened_at = time.monotonic()
                log.warning(
                    "circuit_breaker.opened",
                    name=self._name,
                    failure_count=self._failure_count,
                    reset_after_s=self._reset_after,
                )

    # --- internals ---

    def _maybe_transition_to_half_open(self) -> None:
        """If we are OPEN and the cooldown has elapsed, allow one probe."""
        if (
            self._state is State.OPEN
            and self._opened_at is not None
            and (time.monotonic() - self._opened_at) >= self._reset_after
        ):
            self._state = State.HALF_OPEN
            log.info("circuit_breaker.half_open", name=self._name)

    def _seconds_until_half_open(self) -> float:
        if self._opened_at is None:
            return 0.0
        elapsed = time.monotonic() - self._opened_at
        return max(0.0, self._reset_after - elapsed)
