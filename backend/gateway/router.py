"""Multi-model gateway router with dynamic provider selection.

Routes requests to appropriate providers based on complexity, availability, and cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.gateway.base import LLMProvider, ProviderResponse
from backend.gateway.circuit_breaker import get_circuit_breaker
from backend.gateway.complexity import get_complexity_analyzer, get_cost_calculator


@dataclass
class RoutingDecision:
    """Decision made by the router."""

    selected_provider: LLMProvider | None
    fallback_providers: list[LLMProvider]
    complexity_level: str
    reason: str
    tried_providers: list[str]
    final_error: str | None = None


class ModelGateway:
    """Routes requests to appropriate LLM provider."""

    _instance: ModelGateway | None = None

    def __new__(cls) -> ModelGateway:
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize gateway."""
        if self._initialized:
            return

        self.providers: dict[str, LLMProvider] = {}
        self.provider_priority: list[str] = []
        self.complexity_analyzer = get_complexity_analyzer()
        self.cost_calculator = get_cost_calculator()
        self._initialized = True

    def register_provider(self, provider: LLMProvider, priority: int = 0) -> None:
        """Register a provider with priority.

        Lower priority number = higher priority.
        """
        self.providers[provider.name] = provider

        # Insert in priority order
        if not self.provider_priority:
            self.provider_priority.append(provider.name)
        else:
            inserted = False
            for i, existing_name in enumerate(self.provider_priority):
                if priority < i:
                    self.provider_priority.insert(i, provider.name)
                    inserted = True
                    break
            if not inserted:
                self.provider_priority.append(provider.name)

    def get_provider_by_name(self, name: str) -> LLMProvider | None:
        """Get a specific provider by name."""
        return self.providers.get(name)

    def get_available_providers(self) -> list[str]:
        """Get list of available providers (circuits not open)."""
        available = []
        for name in self.provider_priority:
            breaker = get_circuit_breaker(name)
            is_available, _ = breaker.is_available()
            if is_available:
                available.append(name)
        return available

    async def route(
        self,
        query: str,
        context: str = "",
        num_hits: int = 0,
        use_rerank: bool = False,
    ) -> tuple[ProviderResponse | None, RoutingDecision]:
        """Route request to appropriate provider.

        Args:
            query: User query/prompt
            context: Context for the request
            num_hits: Number of search results
            use_rerank: Whether reranking is needed

        Returns:
            (ProviderResponse, RoutingDecision) - response may be None if all fail
        """
        # Analyze complexity
        analysis = self.complexity_analyzer.analyze(query, context, num_hits, use_rerank)

        # Check budget
        remaining = self.cost_calculator.get_remaining_budget()
        if remaining <= 0:
            return None, RoutingDecision(
                selected_provider=None,
                fallback_providers=[],
                complexity_level=analysis.level.value,
                reason="Budget exceeded",
                tried_providers=[],
                final_error="Monthly budget exhausted",
            )

        # Get providers in priority order
        tried_providers: list[str] = []
        error_messages: list[str] = []

        for provider_name in self.provider_priority:
            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]
            tried_providers.append(provider_name)

            # Check circuit breaker
            breaker = get_circuit_breaker(provider_name)
            is_available, circuit_reason = breaker.is_available()

            if not is_available:
                error_messages.append(f"{provider_name}: {circuit_reason}")
                continue

            # Try provider
            try:
                response = await provider.generate(
                    prompt=query,
                    context=context,
                    model_name=analysis.recommended_model,
                    max_tokens=min(2000, analysis.estimated_tokens * 2),
                )

                # Record success
                breaker.record_success()
                self.cost_calculator.add_spend(provider_name, response.cost_usd)

                return response, RoutingDecision(
                    selected_provider=provider,
                    fallback_providers=[self.providers[p] for p in self.provider_priority if p != provider_name and p in self.providers],
                    complexity_level=analysis.level.value,
                    reason=f"Routed to {provider_name} (complexity: {analysis.level.value})",
                    tried_providers=tried_providers,
                )

            except Exception as e:
                error_msg = f"{provider_name}: {str(e)}"
                error_messages.append(error_msg)

                # Record failure
                breaker.record_failure("provider_error")

        # All providers failed
        fallback_providers = []
        final_error = "\n".join(error_messages) if error_messages else "All providers unavailable"

        return None, RoutingDecision(
            selected_provider=None,
            fallback_providers=fallback_providers,
            complexity_level=analysis.level.value,
            reason="No provider available",
            tried_providers=tried_providers,
            final_error=final_error,
        )

    async def health_check_all(self) -> dict[str, Any]:
        """Check health of all providers."""
        health_status = {}

        for name, provider in self.providers.items():
            try:
                is_healthy = await provider.health_check()
                breaker = get_circuit_breaker(name)
                breaker_stats = breaker.get_stats()

                health_status[name] = {
                    "is_healthy": is_healthy,
                    "circuit_state": breaker_stats.state.value,
                    "consecutive_failures": breaker_stats.consecutive_failures,
                    "total_requests": breaker_stats.total_requests,
                    "total_failures": breaker_stats.total_failures,
                }
            except Exception as e:
                health_status[name] = {
                    "is_healthy": False,
                    "error": str(e),
                }

        return health_status

    def get_gateway_stats(self) -> dict[str, Any]:
        """Get overall gateway statistics."""
        return {
            "total_providers": len(self.providers),
            "available_providers": self.get_available_providers(),
            "cost_stats": self.cost_calculator.get_stats(),
            "provider_states": {
                name: get_circuit_breaker(name).get_stats().to_dict()
                for name in self.provider_priority
            },
        }


def get_gateway() -> ModelGateway:
    """Get the model gateway singleton."""
    return ModelGateway()
