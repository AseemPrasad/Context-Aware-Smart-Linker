"""Base provider interfaces for multi-model gateway.

Defines abstract LLMProvider class and data models for provider implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class TokenUsage:
    """Token usage statistics from a provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def is_empty(self) -> bool:
        return self.total_tokens == 0


@dataclass
class ProviderResponse:
    """Response from an LLM provider."""

    text: str
    tokens_used: TokenUsage
    latency_ms: float
    cost_usd: float
    model_used: str
    provider_name: str

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary for logging."""
        return {
            "text": self.text[:100] + "..." if len(self.text) > 100 else self.text,
            "tokens_used": self.tokens_used.total_tokens,
            "latency_ms": round(self.latency_ms, 2),
            "cost_usd": round(self.cost_usd, 4),
            "model_used": self.model_used,
            "provider_name": self.provider_name,
        }


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    provider_name: str
    api_key: str | None = None
    base_url: str | None = None
    model_name: str | None = None
    max_retries: int = 3
    timeout_seconds: float = 30.0
    rate_limit_requests_per_minute: int = 60
    cost_per_1k_input_tokens: float = 0.0
    cost_per_1k_output_tokens: float = 0.0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: ProviderConfig) -> None:
        """Initialize provider with configuration."""
        self.config = config
        self.name = config.provider_name

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        context: str = "",
        model_name: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> ProviderResponse:
        """Generate a response using this provider.

        Args:
            prompt: The main prompt/question
            context: Additional context for the prompt
            model_name: Override model name (uses config default if not provided)
            max_tokens: Maximum tokens in response
            temperature: Temperature for generation (0.0-1.0)

        Returns:
            ProviderResponse with generated text and metrics
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available and responsive."""
        pass

    def get_provider_name(self) -> str:
        """Get the name of this provider."""
        return self.name

    def calculate_cost(self, tokens_used: TokenUsage) -> float:
        """Calculate cost for token usage."""
        input_cost = (tokens_used.prompt_tokens / 1000.0) * self.config.cost_per_1k_input_tokens
        output_cost = (tokens_used.completion_tokens / 1000.0) * self.config.cost_per_1k_output_tokens
        return input_cost + output_cost

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
