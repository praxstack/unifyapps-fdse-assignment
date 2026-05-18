"""Circuit breaker state-machine tests."""

from __future__ import annotations

import time

import pytest

from agentic_onboard.circuit_breaker import CircuitBreaker, CircuitOpenError, State


@pytest.fixture
def breaker() -> CircuitBreaker:
    return CircuitBreaker(failure_threshold=3, reset_after_s=0.1, name="test")


class TestCircuitBreaker:
    def test_starts_closed(self, breaker: CircuitBreaker) -> None:
        assert breaker.state is State.CLOSED
        breaker.before_call()  # does not raise

    def test_opens_after_threshold_failures(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state is State.OPEN

    def test_open_breaker_rejects_calls(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()
        with pytest.raises(CircuitOpenError) as exc_info:
            breaker.before_call()
        assert exc_info.value.retry_after_s > 0

    def test_success_resets_failure_count(self, breaker: CircuitBreaker) -> None:
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2
        breaker.record_success()
        assert breaker.failure_count == 0
        # Now we should be able to fail twice more before tripping.
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state is State.CLOSED

    def test_transitions_to_half_open_after_cooldown(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state is State.OPEN
        time.sleep(0.15)  # > reset_after_s
        # Touching .state triggers the OPEN→HALF_OPEN transition check.
        assert breaker.state is State.HALF_OPEN

    def test_half_open_success_closes_breaker(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()
        time.sleep(0.15)
        # Probe (HALF_OPEN) and succeed
        breaker.before_call()
        breaker.record_success()
        assert breaker.state is State.CLOSED
        assert breaker.failure_count == 0

    def test_half_open_failure_reopens(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()
        time.sleep(0.15)
        breaker.before_call()  # transitions to HALF_OPEN
        breaker.record_failure()
        assert breaker.state is State.OPEN

    def test_invalid_threshold_rejected(self) -> None:
        with pytest.raises(ValueError, match="failure_threshold"):
            CircuitBreaker(failure_threshold=0)
        with pytest.raises(ValueError, match="reset_after_s"):
            CircuitBreaker(reset_after_s=0)
