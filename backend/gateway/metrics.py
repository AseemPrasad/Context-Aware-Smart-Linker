"""Token tracking and rate limiting metrics for multi-model gateway."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RateLimitWindow:
    """Token rate limit window."""

    window_size_seconds: int = 60
    max_tokens: int = 10000  # Max tokens per minute
    timestamps: deque = field(default_factory=deque)  # (timestamp, tokens) tuples


class ProviderMetrics:
    """Metrics for a single provider."""

    def __init__(self, provider_name: str) -> None:
        """Initialize provider metrics."""
        self.provider_name = provider_name
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_errors = 0
        self.total_latency_ms = 0.0
        self.latencies: deque = deque(maxlen=100)  # Keep last 100

        # Rate limiting
        self.rate_limit_window = RateLimitWindow()
        self.is_rate_limited = False

    def increment(
        self,
        tokens_used: int,
        cost_usd: float,
        latency_ms: float,
        is_error: bool = False,
    ) -> None:
        """Record a request."""
        self.total_requests += 1
        self.total_tokens += tokens_used
        self.total_cost += cost_usd
        self.total_latency_ms += latency_ms
        self.latencies.append(latency_ms)

        if is_error:
            self.total_errors += 1

        # Check rate limit
        now = time.time()
        self.rate_limit_window.timestamps.append((now, tokens_used))

        # Remove expired entries
        while self.rate_limit_window.timestamps:
            oldest_time, _ = self.rate_limit_window.timestamps[0]
            if now - oldest_time > self.rate_limit_window.window_size_seconds:
                self.rate_limit_window.timestamps.popleft()
            else:
                break

        # Check if rate limited
        window_tokens = sum(t for _, t in self.rate_limit_window.timestamps)
        self.is_rate_limited = window_tokens > self.rate_limit_window.max_tokens

    def get_average_latency(self) -> float:
        """Get average latency in milliseconds."""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    def get_error_rate(self) -> float:
        """Get error rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.total_errors / self.total_requests) * 100.0

    def get_remaining_quota(self) -> int:
        """Get remaining token quota for current window."""
        window_tokens = sum(t for _, t in self.rate_limit_window.timestamps)
        return max(0, self.rate_limit_window.max_tokens - window_tokens)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "provider": self.provider_name,
            "requests": self.total_requests,
            "tokens_used": self.total_tokens,
            "cost_usd": round(self.total_cost, 4),
            "errors": self.total_errors,
            "error_rate_percent": round(self.get_error_rate(), 1),
            "avg_latency_ms": round(self.get_average_latency(), 2),
            "rate_limited": self.is_rate_limited,
            "remaining_quota": self.get_remaining_quota(),
        }


class MetricsCollector:
    """Collects metrics across all providers."""

    _instance: MetricsCollector | None = None

    def __new__(cls) -> MetricsCollector:
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize metrics collector."""
        if self._initialized:
            return

        self.provider_metrics: dict[str, ProviderMetrics] = {}
        self._initialized = True

    def get_or_create_metrics(self, provider_name: str) -> ProviderMetrics:
        """Get or create metrics for a provider."""
        if provider_name not in self.provider_metrics:
            self.provider_metrics[provider_name] = ProviderMetrics(provider_name)
        return self.provider_metrics[provider_name]

    def record_request(
        self,
        provider_name: str,
        tokens_used: int,
        cost_usd: float,
        latency_ms: float,
        is_error: bool = False,
    ) -> None:
        """Record a request to a provider."""
        metrics = self.get_or_create_metrics(provider_name)
        metrics.increment(tokens_used, cost_usd, latency_ms, is_error)

    def get_metrics(self, provider_name: str) -> ProviderMetrics | None:
        """Get metrics for a provider."""
        return self.provider_metrics.get(provider_name)

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get all provider metrics."""
        return {
            name: metrics.to_dict()
            for name, metrics in self.provider_metrics.items()
        }

    def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all providers."""
        total_requests = sum(m.total_requests for m in self.provider_metrics.values())
        total_tokens = sum(m.total_tokens for m in self.provider_metrics.values())
        total_cost = sum(m.total_cost for m in self.provider_metrics.values())
        total_errors = sum(m.total_errors for m in self.provider_metrics.values())

        all_latencies = []
        for metrics in self.provider_metrics.values():
            all_latencies.extend(metrics.latencies)

        avg_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0.0

        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 2),
            "total_errors": total_errors,
            "error_rate_percent": round((total_errors / total_requests * 100) if total_requests > 0 else 0.0, 1),
            "avg_latency_ms": round(avg_latency, 2),
            "providers_count": len(self.provider_metrics),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.provider_metrics = {}


def get_metrics_collector() -> MetricsCollector:
    """Get the metrics collector singleton."""
    return MetricsCollector()
