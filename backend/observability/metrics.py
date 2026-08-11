"""Token budgeting and Prometheus metrics engine.

Tracks token consumption per tenant/model/route and enforces soft budget limits.
"""

import os
import logging
from typing import Optional, Dict
from dataclasses import dataclass, field

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


@dataclass
class TenantBudget:
    """Monthly token budget for a tenant."""

    tenant_id: str
    monthly_budget_usd: float
    warn_threshold: float = 0.8  # Warn at 80% usage
    tokens_consumed: float = 0.0
    cost_consumed_usd: float = 0.0


class MetricsConfig:
    """Configuration for token metrics and budgeting."""

    def __init__(self):
        self.enabled = os.getenv("TOKEN_METRICS_ENABLED", "false").lower() == "true"
        self.default_budget_usd = float(os.getenv("TENANT_MONTHLY_BUDGET_USD", "100.0"))
        self.warn_threshold = float(os.getenv("TENANT_BUDGET_WARN_THRESHOLD", "0.8"))
        self.cost_per_1k_input = float(os.getenv("COST_PER_1K_INPUT_TOKENS", "0.0015"))
        self.cost_per_1k_output = float(os.getenv("COST_PER_1K_OUTPUT_TOKENS", "0.006"))


class TokenCounter:
    """Prometheus metrics for token tracking."""

    def __init__(self):
        self.tokens_consumed_total = Counter(
            "tokens_consumed_total",
            "Total tokens consumed",
            labelnames=["tenant_id", "model", "route"],
        )
        self.tokens_input_total = Counter(
            "tokens_input_total",
            "Total input tokens",
            labelnames=["tenant_id", "model"],
        )
        self.tokens_output_total = Counter(
            "tokens_output_total",
            "Total output tokens",
            labelnames=["tenant_id", "model"],
        )
        self.cost_usd_total = Counter(
            "cost_usd_total",
            "Total cost in USD",
            labelnames=["tenant_id", "model"],
        )
        self.budget_remaining_by_tenant = Gauge(
            "budget_remaining_usd",
            "Remaining budget in USD",
            labelnames=["tenant_id"],
        )
        self.llm_latency_ms = Histogram(
            "llm_latency_ms",
            "LLM inference latency in milliseconds",
            labelnames=["provider", "model"],
            buckets=(50, 100, 200, 500, 1000, 2000, 5000),
        )
        self.cache_hit_rate = Gauge(
            "cache_hit_rate",
            "Cache hit rate (0-1)",
            labelnames=["cache_type"],
        )
        self.cache_lookup_latency_ms = Histogram(
            "cache_lookup_latency_ms",
            "Cache lookup latency in milliseconds",
            labelnames=["cache_type"],
            buckets=(1, 5, 10, 25, 50, 100),
        )


class TokenBudgetManager:
    """Manages per-tenant token budgets and cost tracking."""

    def __init__(self, config: Optional[MetricsConfig] = None):
        self.config = config or MetricsConfig()
        self.counter = TokenCounter()
        self.tenants: Dict[str, TenantBudget] = {}
        self.enabled = self.config.enabled

        logger.info(
            f"TokenBudgetManager initialized (enabled={self.enabled}, "
            f"default_budget=${self.config.default_budget_usd})"
        )

    def get_or_create_tenant(self, tenant_id: str) -> TenantBudget:
        """Get or create budget entry for tenant."""
        if tenant_id not in self.tenants:
            self.tenants[tenant_id] = TenantBudget(
                tenant_id=tenant_id,
                monthly_budget_usd=self.config.default_budget_usd,
                warn_threshold=self.config.warn_threshold,
            )
        return self.tenants[tenant_id]

    def record_tokens(
        self,
        tenant_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        route: str = "unknown",
    ) -> None:
        """Record token usage and update Prometheus metrics.

        Args:
            tenant_id: Tenant identifier
            model: Model name (e.g., 'gpt-4', 'claude-3')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            route: API route (e.g., 'search', 'stream')
        """
        if not self.enabled:
            return

        try:
            total_tokens = input_tokens + output_tokens
            input_cost = (input_tokens / 1000.0) * self.config.cost_per_1k_input
            output_cost = (output_tokens / 1000.0) * self.config.cost_per_1k_output
            total_cost = input_cost + output_cost

            budget = self.get_or_create_tenant(tenant_id)
            budget.tokens_consumed += total_tokens
            budget.cost_consumed_usd += total_cost

            self.counter.tokens_consumed_total.labels(
                tenant_id=tenant_id, model=model, route=route
            ).inc(total_tokens)
            self.counter.tokens_input_total.labels(tenant_id=tenant_id, model=model).inc(input_tokens)
            self.counter.tokens_output_total.labels(tenant_id=tenant_id, model=model).inc(output_tokens)
            self.counter.cost_usd_total.labels(tenant_id=tenant_id, model=model).inc(total_cost)

            remaining = budget.monthly_budget_usd - budget.cost_consumed_usd
            self.counter.budget_remaining_by_tenant.labels(tenant_id=tenant_id).set(max(0, remaining))

            logger.debug(
                f"Recorded tokens for {tenant_id}: {total_tokens} tokens, "
                f"${total_cost:.4f} cost (remaining: ${remaining:.2f})"
            )

        except Exception as e:
            logger.error(f"Error recording tokens: {e}")

    def get_remaining_budget(self, tenant_id: str) -> float:
        """Get remaining budget for tenant in USD."""
        budget = self.get_or_create_tenant(tenant_id)
        return max(0, budget.monthly_budget_usd - budget.cost_consumed_usd)

    def check_budget_exceeded(self, tenant_id: str) -> tuple[bool, Optional[str]]:
        """Check if tenant has exceeded budget.

        Returns:
            (exceeded: bool, warning_message: Optional[str])
        """
        if not self.enabled:
            return False, None

        budget = self.get_or_create_tenant(tenant_id)
        remaining = self.get_remaining_budget(tenant_id)
        usage_pct = (budget.cost_consumed_usd / budget.monthly_budget_usd) * 100

        if remaining <= 0:
            return True, f"Tenant {tenant_id} has exceeded monthly budget (${usage_pct:.1f}% used)"

        if usage_pct >= (budget.warn_threshold * 100):
            return False, f"Warning: Tenant {tenant_id} at {usage_pct:.1f}% of monthly budget"

        return False, None

    def get_metrics(self) -> dict:
        """Get aggregated metrics for all tenants."""
        metrics = {"tenants": {}, "enabled": self.enabled}

        for tenant_id, budget in self.tenants.items():
            metrics["tenants"][tenant_id] = {
                "tokens_consumed": budget.tokens_consumed,
                "cost_usd": round(budget.cost_consumed_usd, 4),
                "remaining_budget_usd": round(self.get_remaining_budget(tenant_id), 2),
                "usage_percent": round((budget.cost_consumed_usd / budget.monthly_budget_usd) * 100, 1),
            }

        return metrics


_budget_manager: Optional[TokenBudgetManager] = None


def get_token_budget_manager() -> TokenBudgetManager:
    """Get singleton token budget manager."""
    global _budget_manager

    if _budget_manager is None:
        _budget_manager = TokenBudgetManager()

    return _budget_manager
