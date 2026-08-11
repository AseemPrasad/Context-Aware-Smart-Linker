"""Ollama provider implementation for multi-model gateway.

Ollama enables running open-source LLMs locally as fallback.
"""

from __future__ import annotations

import json
import time
from typing import Any

import aiohttp

from backend.gateway.base import LLMProvider, ProviderConfig, ProviderResponse, TokenUsage


class OllamaProvider(LLMProvider):
    """Ollama provider for local LLM inference."""

    def __init__(self, config: ProviderConfig) -> None:
        """Initialize Ollama provider."""
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def generate(
        self,
        prompt: str,
        context: str = "",
        model_name: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> ProviderResponse:
        """Generate response using Ollama API."""
        model = model_name or self.config.model_name or "mistral"
        full_prompt = f"{context}\n\n{prompt}" if context else prompt

        start_time = time.time()
        session = await self._get_session()

        try:
            response = await session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": full_prompt,
                    "stream": False,
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
            )

            if response.status != 200:
                raise RuntimeError(f"Ollama API returned status {response.status}")

            data = await response.json()

            latency_ms = (time.time() - start_time) * 1000

            # Ollama doesn't provide token counts, estimate them
            text = data.get("response", "")
            tokens_used = TokenUsage(
                prompt_tokens=len(full_prompt) // 4,  # Rough estimate
                completion_tokens=len(text) // 4,
                total_tokens=(len(full_prompt) + len(text)) // 4,
            )

            # Ollama is local, so zero cost
            cost = 0.0

            return ProviderResponse(
                text=text,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                cost_usd=cost,
                model_used=model,
                provider_name=self.name,
            )

        except aiohttp.ClientConnectorError:
            raise RuntimeError("Ollama server not available")
        except asyncio.TimeoutError:
            raise RuntimeError("Ollama request timeout")
        except Exception as e:
            raise RuntimeError(f"Ollama API error: {str(e)}")

    async def health_check(self) -> bool:
        """Check if Ollama server is available."""
        try:
            session = await self._get_session()
            response = await session.get(
                f"{self.base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5.0),
            )
            return response.status == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None

    def __del__(self) -> None:
        """Cleanup on deletion."""
        if self._session:
            try:
                import asyncio
                asyncio.run(self.close())
            except Exception:
                pass


def get_ollama_provider(config: ProviderConfig) -> OllamaProvider:
    """Get Ollama provider instance."""
    return OllamaProvider(config)


# Import asyncio for type hints
import asyncio
