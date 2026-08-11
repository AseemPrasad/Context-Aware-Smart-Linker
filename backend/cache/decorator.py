"""Decorator for seamlessly integrating cache into endpoints.

Wraps endpoint functions with pre-call cache lookup and post-call cache write
without modifying the original function logic.
"""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable

from backend.cache.semantic_cache import SemanticCache
from backend.schemas.retrieval import SearchRequest, SearchResponse


def with_semantic_cache(
    func: Callable,
) -> Callable:
    """Decorator to wrap search endpoint with caching.

    Adds pre-call cache lookup and async post-call cache write.
    Gracefully handles cache unavailability without affecting the response.
    """

    @functools.wraps(func)
    async def wrapper(
        request: SearchRequest,
        cache: SemanticCache | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        # Tier 1 + Tier 2 cache lookup
        if cache:
            cached_response = cache.get(request)
            if cached_response:
                return cached_response

        # Cache miss: execute original function
        response: SearchResponse = await func(request, **kwargs)

        # Async write to cache (non-blocking, fire-and-forget)
        if cache:
            asyncio.create_task(_write_cache_async(cache, request, response))

        return response

    return wrapper


async def _write_cache_async(
    cache: SemanticCache,
    request: SearchRequest,
    response: SearchResponse,
) -> None:
    """Async task for writing cache (runs in background, never awaited)."""
    # Run in thread pool to avoid blocking event loop
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cache.set, request, response)
