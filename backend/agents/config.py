"""Agent cost control and performance optimization configuration."""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class PerformanceTuning:
    """Performance optimization settings for agent execution."""

    def __init__(self):
        # Parallelization
        self.parallel_searches = os.getenv("AGENTS_PARALLEL_SEARCHES", "true").lower() == "true"
        self.max_concurrent_searches = int(os.getenv("AGENTS_MAX_CONCURRENT_SEARCHES", "5"))

        # Caching
        self.cache_search_results = os.getenv("AGENTS_CACHE_SEARCH_RESULTS", "true").lower() == "true"
        self.cache_ttl_hours = int(os.getenv("AGENTS_CACHE_TTL_HOURS", "24"))

        # Early termination
        self.skip_verifier_on_empty_results = os.getenv("AGENTS_SKIP_VERIFIER_ON_EMPTY", "true").lower() == "true"

        # LLM response caching
        self.cache_llm_responses = os.getenv("AGENTS_CACHE_LLM_RESPONSES", "true").lower() == "true"

        logger.info(
            f"PerformanceTuning: "
            f"parallel_searches={self.parallel_searches}, "
            f"cache_enabled={self.cache_search_results}"
        )


class CostModel:
    """Cost estimation and tracking for agent execution."""

    # Per-call pricing (USD)
    LLM_COSTS = {
        "gpt-3.5-turbo": 0.001,  # $0.0015 per 1K input, $0.002 per 1K output
        "gpt-4": 0.03,  # $0.03 per 1K input, $0.06 per 1K output
        "claude-3": 0.003,  # $0.003 per 1K input, $0.015 per 1K output
    }

    SEARCH_COSTS = {
        "tavily": 0.0,  # Free tier (1000/month)
        "serper": 0.0,  # Free tier with low limits
    }

    @staticmethod
    def estimate_llm_cost(calls_per_request: int = 2, model: str = "gpt-3.5-turbo") -> float:
        """Estimate LLM cost per request.

        Args:
            calls_per_request: Number of LLM calls (planner, verifier)
            model: Model name

        Returns:
            Estimated cost in USD
        """
        cost_per_call = CostModel.LLM_COSTS.get(model, 0.001)
        return calls_per_request * cost_per_call

    @staticmethod
    def estimate_search_cost(searches_per_request: int = 3, provider: str = "tavily") -> float:
        """Estimate search API cost per request.

        Args:
            searches_per_request: Number of searches
            provider: Search provider name

        Returns:
            Estimated cost in USD
        """
        cost_per_search = CostModel.SEARCH_COSTS.get(provider, 0.0)
        return searches_per_request * cost_per_search

    @staticmethod
    def estimate_total_cost(
        llm_calls: int = 2,
        searches: int = 3,
        llm_model: str = "gpt-3.5-turbo",
        search_provider: str = "tavily",
    ) -> float:
        """Estimate total cost per request.

        Args:
            llm_calls: Number of LLM calls
            searches: Number of searches
            llm_model: LLM model
            search_provider: Search provider

        Returns:
            Estimated cost in USD
        """
        llm_cost = CostModel.estimate_llm_cost(llm_calls, llm_model)
        search_cost = CostModel.estimate_search_cost(searches, search_provider)
        return llm_cost + search_cost

    @staticmethod
    def estimate_monthly_cost(
        requests_per_month: int = 1000,
        llm_calls: int = 2,
        searches: int = 3,
        llm_model: str = "gpt-3.5-turbo",
        search_provider: str = "tavily",
    ) -> float:
        """Estimate monthly agent cost.

        Args:
            requests_per_month: Expected requests per month
            llm_calls: LLM calls per request
            searches: Searches per request
            llm_model: LLM model
            search_provider: Search provider

        Returns:
            Estimated monthly cost in USD
        """
        per_request = CostModel.estimate_total_cost(llm_calls, searches, llm_model, search_provider)
        return per_request * requests_per_month


class CircuitBreaker:
    """Circuit breaker for disabling agents on high latency."""

    def __init__(self):
        self.latency_threshold_ms = int(os.getenv("AGENTS_LATENCY_THRESHOLD_MS", "5000"))
        self.failure_threshold = int(os.getenv("AGENTS_FAILURE_THRESHOLD", "5"))
        self.recovery_time_seconds = int(os.getenv("AGENTS_RECOVERY_TIME_SECONDS", "600"))

        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        self.last_failure_time = None

    async def check_health(self, latency_ms: float) -> bool:
        """Check if agents should be active based on latency.

        Args:
            latency_ms: Execution latency in milliseconds

        Returns:
            True if agents should remain active
        """
        if latency_ms > self.latency_threshold_ms:
            self.failure_count += 1
            logger.warning(
                f"High latency detected: {latency_ms:.1f}ms "
                f"(failures: {self.failure_count}/{self.failure_threshold})"
            )

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(f"Circuit breaker OPEN: Disabling agents for {self.recovery_time_seconds}s")
                return False

        else:
            self.failure_count = max(0, self.failure_count - 1)

        return self.state != "OPEN"


class AgentConfigAdvanced:
    """Extended agent configuration with cost and performance controls."""

    def __init__(self):
        # Core settings
        self.enabled = os.getenv("AGENTS_ENABLED", "false").lower() == "true"
        self.max_retries = int(os.getenv("AGENTS_MAX_RETRIES", "3"))
        self.timeout_seconds = int(os.getenv("AGENTS_TIMEOUT_SECONDS", "30"))
        self.search_provider = os.getenv("AGENTS_SEARCH_PROVIDER", "tavily")
        self.streaming_enabled = os.getenv("AGENTS_STREAMING_ENABLED", "false").lower() == "true"

        # API keys
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self.serper_api_key = os.getenv("SERPER_API_KEY", "")

        # Cost control
        self.max_monthly_cost_usd = float(os.getenv("AGENTS_MAX_MONTHLY_COST_USD", "100.0"))
        self.llm_model = os.getenv("AGENTS_LLM_MODEL", "gpt-3.5-turbo")

        # Performance tuning
        self.perf_tuning = PerformanceTuning()
        self.circuit_breaker = CircuitBreaker()

        logger.info(
            f"AgentConfigAdvanced initialized: "
            f"enabled={self.enabled}, "
            f"max_cost=${self.max_monthly_cost_usd}/month, "
            f"estimated=${CostModel.estimate_monthly_cost(model=self.llm_model):.2f}/month"
        )

    def get_cost_estimate(self, requests_per_month: int = 1000) -> Dict[str, Any]:
        """Get cost estimate for agent execution.

        Args:
            requests_per_month: Expected monthly requests

        Returns:
            Cost breakdown dictionary
        """
        per_request = CostModel.estimate_total_cost(
            llm_model=self.llm_model, search_provider=self.search_provider
        )
        monthly = per_request * requests_per_month

        return {
            "per_request_usd": round(per_request, 4),
            "monthly_estimate_usd": round(monthly, 2),
            "max_budget_usd": self.max_monthly_cost_usd,
            "budget_utilization": f"{(monthly / self.max_monthly_cost_usd * 100):.1f}%",
            "within_budget": monthly <= self.max_monthly_cost_usd,
        }


def print_cost_breakdown(requests_per_month: int = 1000) -> None:
    """Print cost breakdown for agent execution.

    Args:
        requests_per_month: Requests per month for projection
    """
    print("\n" + "=" * 80)
    print("AGENT EXECUTION COST BREAKDOWN")
    print("=" * 80 + "\n")

    # By LLM model
    print("Cost by LLM Model (per request):")
    print("-" * 80)
    for model in ["gpt-3.5-turbo", "gpt-4", "claude-3"]:
        cost = CostModel.estimate_total_cost(llm_model=model)
        monthly = cost * requests_per_month
        print(f"  {model:20} | ${cost:7.4f}/req | ${monthly:7.2f}/month")

    # By search provider
    print("\nSearch Provider Cost (per request):")
    print("-" * 80)
    for provider in ["tavily", "serper"]:
        cost = CostModel.estimate_search_cost(provider=provider)
        print(f"  {provider:20} | ${cost:7.4f}/req | Free tier")

    # Summary
    print("\nSummary (GPT-3.5 + Tavily):")
    print("-" * 80)
    estimated = CostModel.estimate_monthly_cost()
    print(f"  Requests/month:     {requests_per_month:,}")
    print(f"  Cost/request:       ${CostModel.estimate_total_cost():.4f}")
    print(f"  Estimated/month:    ${estimated:.2f}")

    print("\n" + "=" * 80)


def get_config() -> AgentConfigAdvanced:
    """Get singleton agent configuration."""
    return AgentConfigAdvanced()
