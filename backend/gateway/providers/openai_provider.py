"""OpenAI provider implementation for multi-model gateway."""

from __future__ import annotations

import time
from typing import Any

from backend.gateway.base import LLMProvider, ProviderConfig, ProviderResponse, TokenUsage


class OpenAIProvider(LLMProvider):
    """OpenAI provider using GPT models."""

    def __init__(self, config: ProviderConfig) -> None:
        """Initialize OpenAI provider."""
        super().__init__(config)
        self._client: Any = None
        self._initialized = False

    def _ensure_client(self) -> None:
        """Lazy initialize OpenAI client."""
        if self._initialized:
            return

        if not self.config.api_key:
            raise ValueError("OpenAI API key not configured")

        try:
            import openai
            openai.api_key = self.config.api_key
            if self.config.base_url:
                openai.base_url = self.config.base_url
            self._client = openai.AsyncOpenAI(api_key=self.config.api_key)
            self._initialized = True
        except ImportError:
            raise ImportError("openai library not installed. Install with: pip install openai")

    async def generate(
        self,
        prompt: str,
        context: str = "",
        model_name: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> ProviderResponse:
        """Generate response using OpenAI API."""
        self._ensure_client()

        model = model_name or self.config.model_name or "gpt-4o-mini"
        full_prompt = f"{context}\n\n{prompt}" if context else prompt

        start_time = time.time()

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": full_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extract usage
            tokens_used = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

            # Calculate cost
            cost = self.calculate_cost(tokens_used)

            # Extract text
            text = response.choices[0].message.content or ""

            return ProviderResponse(
                text=text,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                cost_usd=cost,
                model_used=model,
                provider_name=self.name,
            )

        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    async def health_check(self) -> bool:
        """Check if OpenAI API is available."""
        try:
            self._ensure_client()
            # Verify API key by listing models (doesn't consume quota significantly)
            await self._client.models.list()
            return True
        except Exception:
            return False


def get_openai_provider(config: ProviderConfig) -> OpenAIProvider:
    """Get OpenAI provider instance."""
    return OpenAIProvider(config)
