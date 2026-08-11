"""Circuit breaker pattern for provider resilience.

Implements state machine: CLOSED (normal) -> OPEN (failed) -> HALF_OPEN (recovery).
Prevents cascading failures and enables automatic recovery.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CircuitState(str, Enum):
    """Circuit breaker state."""

    CLOSED = "closed"      # Normal operation, forward all requests
    OPEN = "open"          # Failed, reject requests
    HALF_OPEN = "half_open"  # Recovery phase, allow test request


@dataclass
class CircuitBreakerStats:
    """Statistics for a circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    last_failure_time: datetime | None = None
    last_failure_reason: str | None = None
    last_success_time: datetime | None = None
    total_requests: int = 0
    total_failures: int = 0
    state_change_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_failure_reason": self.last_failure_reason,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "state_change_time": self.state_change_time.isoformat() if self.state_change_time else None,
        }


class CircuitBreaker:
    """Circuit breaker for a provider."""

    _instances: dict[str, CircuitBreaker] = {}

    def __new__(cls, provider_name: str) -> CircuitBreaker:
        """Create or retrieve singleton per provider."""
        if provider_name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[provider_name] = instance
        return cls._instances[provider_name]

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
        half_open_timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            provider_name: Name of the provider
            failure_threshold: Consecutive failures before opening circuit
            cooldown_seconds: Time in OPEN state before transitioning to HALF_OPEN
            half_open_timeout_seconds: Time for test request in HALF_OPEN state
        """
        if hasattr(self, "_initialized"):
            return

        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_timeout_seconds = half_open_timeout_seconds

        self.stats = CircuitBreakerStats()
        self._open_time: float | None = None
        self._half_open_test_time: float | None = None
        self._initialized = True

    def is_available(self) -> tuple[bool, str]:
        """Check if circuit allows requests.

        Returns:
            (is_available: bool, reason: str)
        """
        now = time.time()

        if self.stats.state == CircuitState.CLOSED:
            return True, "Circuit closed, provider available"

        if self.stats.state == CircuitState.OPEN:
            # Check if cooldown elapsed
            if self._open_time and (now - self._open_time) >= self.cooldown_seconds:
                self._transition_to_half_open()
                return True, "Circuit half-open, allowing test request"
            else:
                remaining = self.cooldown_seconds - (now - self._open_time) if self._open_time else self.cooldown_seconds
                return False, f"Circuit open, provider unavailable. Recovery in {remaining:.0f}s"

        if self.stats.state == CircuitState.HALF_OPEN:
            # In half-open, allow test request
            return True, "Circuit half-open, test request allowed"

        return False, "Unknown circuit state"

    def record_success(self) -> None:
        """Record successful request."""
        self.stats.total_requests += 1
        self.stats.last_success_time = datetime.utcnow()

        if self.stats.state == CircuitState.HALF_OPEN:
            # Test request succeeded, close circuit
            self._transition_to_closed()
        elif self.stats.state == CircuitState.CLOSED:
            # Reset failure counter on success
            self.stats.consecutive_failures = 0

    def record_failure(self, reason: str) -> None:
        """Record failed request.

        Args:
            reason: Error reason (e.g., 'rate_limit', 'timeout', 'server_error')
        """
        self.stats.total_requests += 1
        self.stats.total_failures += 1
        self.stats.consecutive_failures += 1
        self.stats.last_failure_time = datetime.utcnow()
        self.stats.last_failure_reason = reason

        if self.stats.state == CircuitState.HALF_OPEN:
            # Test request failed, open circuit again
            self._transition_to_open()
        elif self.stats.state == CircuitState.CLOSED:
            # Check if threshold exceeded
            if self.stats.consecutive_failures >= self.failure_threshold:
                self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        self.stats.state = CircuitState.OPEN
        self.stats.state_change_time = datetime.utcnow()
        self._open_time = time.time()

    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self.stats.state = CircuitState.HALF_OPEN
        self.stats.state_change_time = datetime.utcnow()
        self._half_open_test_time = time.time()
        self.stats.consecutive_failures = 0  # Reset for test

    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        self.stats.state = CircuitState.CLOSED
        self.stats.state_change_time = datetime.utcnow()
        self.stats.consecutive_failures = 0
        self._open_time = None
        self._half_open_test_time = None

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self.stats

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.stats = CircuitBreakerStats()
        self._open_time = None
        self._half_open_test_time = None

    def __repr__(self) -> str:
        return f"CircuitBreaker(provider={self.provider_name}, state={self.stats.state.value})"


def get_circuit_breaker(provider_name: str) -> CircuitBreaker:
    """Get or create circuit breaker for a provider."""
    return CircuitBreaker(provider_name)
