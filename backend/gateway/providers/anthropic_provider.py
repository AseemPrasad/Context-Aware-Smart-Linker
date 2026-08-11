"""Anthropic provider implementation for multi-model gateway."""

from __future__ import annotations

import time
from typing import Any

from backend.gateway.base import LLMProvider, ProviderConfig, ProviderResponse, TokenUsage


class AnthropicProvider(LLMProvider):
    """Anthropic provider using Claude models."""

    def __init__(self, config: ProviderConfig) -> None:
        """Initialize Anthropic provider."""
        super().__init__(config)
        self._client: Any = None
        self._initialized = False

    def _ensure_client(self) -> None:
        """Lazy initialize Anthropic client."""
        if self._initialized:
            return

        if not self.config.api_key:
            raise ValueError("Anthropic API key not configured")

        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
            if self.config.base_url:
                self._client.base_url = self.config.base_url
            self._initialized = True
        except ImportError:
            raise ImportError("anthropic library not installed. Install with: pip install anthropic")

    async def generate(
        self,
        prompt: str,
        context: str = "",
        model_name: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> ProviderResponse:
        """Generate response using Anthropic API."""
        self._ensure_client()

        model = model_name or self.config.model_name or "claude-3-5-sonnet-20241022"
        full_prompt = f"{context}\n\n{prompt}" if context else prompt

        start_time = time.time()

        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system="You are a helpful assistant.",
                messages=[
                    {"role": "user", "content": full_prompt},
                ],
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extract usage
            tokens_used = TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            )

            # Calculate cost
            cost = self.calculate_cost(tokens_used)

            # Extract text
            text = response.content[0].text if response.content else ""

            return ProviderResponse(
                text=text,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                cost_usd=cost,
                model_used=model,
                provider_name=self.name,
            )

        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {str(e)}")

    async def health_check(self) -> bool:
        """Check if Anthropic API is available."""
        try:
            self._ensure_client()
            # Test with a minimal request to verify API key
            response = await self._client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "ok"}],
            )
            return bool(response)
        except Exception:
            return False


def get_anthropic_provider(config: ProviderConfig) -> AnthropicProvider:
    """Get Anthropic provider instance."""
    return AnthropicProvider(config)
