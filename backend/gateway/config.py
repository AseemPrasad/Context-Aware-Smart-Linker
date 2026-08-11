"""Gateway configuration for multi-model routing.

Centralizes all gateway settings with env var support.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class GatewayConfig:
    """Configuration for multi-model gateway."""

    # Master flags
    gateway_enabled: bool = os.getenv("GATEWAY_ENABLED", "false").lower() == "true"
    gateway_mode: str = os.getenv("GATEWAY_MODE", "hybrid")  # hybrid, fallback_only, disabled

    # Provider settings
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_cost_input: float = float(os.getenv("OPENAI_COST_INPUT", "0.00003"))  # Per 1K tokens
    openai_cost_output: float = float(os.getenv("OPENAI_COST_OUTPUT", "0.0006"))

    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    anthropic_cost_input: float = float(os.getenv("ANTHROPIC_COST_INPUT", "0.003"))  # Per 1K tokens
    anthropic_cost_output: float = float(os.getenv("ANTHROPIC_COST_OUTPUT", "0.015"))

    ollama_enabled: bool = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "mistral")

    # Circuit breaker settings
    circuit_breaker_failure_threshold: int = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    circuit_breaker_cooldown_seconds: float = float(os.getenv("CIRCUIT_BREAKER_COOLDOWN_SECONDS", "60"))
    circuit_breaker_half_open_timeout: float = float(os.getenv("CIRCUIT_BREAKER_HALF_OPEN_TIMEOUT", "30"))

    # Budget settings
    monthly_budget_usd: float = float(os.getenv("MONTHLY_BUDGET_USD", "100"))
    budget_warning_threshold_percent: float = float(os.getenv("BUDGET_WARNING_THRESHOLD", "80"))

    # Provider priority order (comma-separated)
    provider_priority: list[str] = []

    # Complexity routing
    complexity_routing_enabled: bool = os.getenv("COMPLEXITY_ROUTING_ENABLED", "true").lower() == "true"
    cost_aware_routing_enabled: bool = os.getenv("COST_AWARE_ROUTING_ENABLED", "true").lower() == "true"

    # Rate limiting
    rate_limit_tokens_per_minute: int = int(os.getenv("RATE_LIMIT_TOKENS_PER_MINUTE", "10000"))

    def __post_init__(self) -> None:
        """Validate and finalize configuration."""
        # Parse provider priority from env var
        priority_str = os.getenv("PROVIDER_PRIORITY_ORDER", "openai,anthropic,ollama")
        self.provider_priority = [p.strip() for p in priority_str.split(",") if p.strip()]

        # Validate mode
        if self.gateway_mode not in ("hybrid", "fallback_only", "disabled"):
            raise ValueError(f"Invalid gateway_mode: {self.gateway_mode}")

    def get_enabled_providers(self) -> list[str]:
        """Get list of enabled providers."""
        enabled = []

        if self.openai_api_key:
            enabled.append("openai")

        if self.anthropic_api_key:
            enabled.append("anthropic")

        if self.ollama_enabled:
            enabled.append("ollama")

        # Filter by priority order
        ordered = [p for p in self.provider_priority if p in enabled]
        return ordered if ordered else enabled

    def is_gateway_active(self) -> bool:
        """Check if gateway should be active."""
        if not self.gateway_enabled:
            return False

        if self.gateway_mode == "disabled":
            return False

        # Need at least one provider configured
        return len(self.get_enabled_providers()) > 0

    def get_provider_config(self, provider_name: str) -> dict:
        """Get configuration for a specific provider."""
        if provider_name == "openai":
            return {
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "cost_input": self.openai_cost_input,
                "cost_output": self.openai_cost_output,
            }
        elif provider_name == "anthropic":
            return {
                "api_key": self.anthropic_api_key,
                "model": self.anthropic_model,
                "cost_input": self.anthropic_cost_input,
                "cost_output": self.anthropic_cost_output,
            }
        elif provider_name == "ollama":
            return {
                "base_url": self.ollama_base_url,
                "model": self.ollama_model,
                "cost_input": 0.0,
                "cost_output": 0.0,
            }
        else:
            raise ValueError(f"Unknown provider: {provider_name}")


def get_gateway_config() -> GatewayConfig:
    """Get the gateway configuration singleton."""
    if not hasattr(get_gateway_config, "_instance"):
        get_gateway_config._instance = GatewayConfig()
    return get_gateway_config._instance
