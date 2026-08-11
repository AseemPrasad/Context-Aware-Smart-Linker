"""External search tool integrations (Tavily, Serper).

Provides pluggable search provider abstraction for fetching live references.
"""

import logging
import asyncio
from typing import List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from external search."""

    title: str
    url: str
    snippet: str
    confidence: Optional[float] = None


class SearchProvider(ABC):
    """Abstract base class for search providers."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search for query.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
        pass


class TavilySearchProvider(SearchProvider):
    """Tavily search API provider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.name = "tavily"
        self.rate_limiter = RateLimiter(requests_per_minute=10)
        self.cache = SearchResultCache(ttl_hours=24)

        if not self.api_key:
            logger.warning("Tavily API key not configured")

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search via Tavily API.

        Args:
            query: Search query
            max_results: Max results to return

        Returns:
            List of search results
        """
        if not self.api_key:
            logger.warning("Tavily API key not set, returning empty results")
            return []

        # Check cache first
        cached = self.cache.get(query)
        if cached:
            logger.debug(f"Cache hit for query: {query}")
            return cached[:max_results]

        # Rate limiting
        await self.rate_limiter.acquire()

        try:
            # Placeholder: In production, would make actual API call
            # import tavily  # pip install tavily-python
            # client = tavily.TavilyClient(api_key=self.api_key)
            # response = await asyncio.to_thread(client.search, query, max_results=max_results)

            results = [
                SearchResult(
                    title=f"Tavily result for '{query}'",
                    url=f"https://example.com/tavily-{hash(query) % 1000}",
                    snippet=f"Search result snippet from Tavily for: {query}",
                    confidence=0.8,
                )
            ]

            # Cache results
            self.cache.set(query, results)

            logger.info(f"Tavily search for '{query}': {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Tavily search failed for '{query}': {e}")
            return []

    async def health_check(self) -> bool:
        """Check Tavily availability."""
        # Placeholder: Would make actual API call
        return bool(self.api_key)


class SerperSearchProvider(SearchProvider):
    """Serper search API provider (alternative to Tavily)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.name = "serper"
        self.rate_limiter = RateLimiter(requests_per_minute=10)
        self.cache = SearchResultCache(ttl_hours=24)

        if not self.api_key:
            logger.warning("Serper API key not configured")

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search via Serper API.

        Args:
            query: Search query
            max_results: Max results to return

        Returns:
            List of search results
        """
        if not self.api_key:
            logger.warning("Serper API key not set, returning empty results")
            return []

        # Check cache first
        cached = self.cache.get(query)
        if cached:
            logger.debug(f"Cache hit for query: {query}")
            return cached[:max_results]

        # Rate limiting
        await self.rate_limiter.acquire()

        try:
            # Placeholder: In production, would make actual API call
            # import requests
            # response = requests.get("https://google.serper.dev/search", ...)

            results = [
                SearchResult(
                    title=f"Serper result for '{query}'",
                    url=f"https://example.com/serper-{hash(query) % 1000}",
                    snippet=f"Search result snippet from Serper for: {query}",
                    confidence=0.8,
                )
            ]

            # Cache results
            self.cache.set(query, results)

            logger.info(f"Serper search for '{query}': {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Serper search failed for '{query}': {e}")
            return []

    async def health_check(self) -> bool:
        """Check Serper availability."""
        # Placeholder: Would make actual API call
        return bool(self.api_key)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.requests = []

    async def acquire(self) -> None:
        """Acquire token, waiting if necessary."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)

        # Remove old requests outside window
        self.requests = [r for r in self.requests if r > cutoff]

        if len(self.requests) >= self.requests_per_minute:
            # Wait until oldest request is outside window
            wait_time = (self.requests[0] - cutoff).total_seconds() + 0.1
            logger.debug(f"Rate limit hit, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            await self.acquire()  # Retry
        else:
            self.requests.append(now)


class SearchResultCache:
    """In-memory cache for search results (with TTL)."""

    def __init__(self, ttl_hours: int = 24):
        self.ttl_hours = ttl_hours
        self.cache: Dict[str, tuple[List[SearchResult], datetime]] = {}

    def get(self, query: str) -> Optional[List[SearchResult]]:
        """Get cached results if available and not expired."""
        if query not in self.cache:
            return None

        results, timestamp = self.cache[query]
        age = (datetime.utcnow() - timestamp).total_seconds() / 3600

        if age > self.ttl_hours:
            del self.cache[query]
            return None

        return results

    def set(self, query: str, results: List[SearchResult]) -> None:
        """Cache search results."""
        self.cache[query] = (results, datetime.utcnow())
        logger.debug(f"Cached {len(results)} results for query: {query}")

    def clear(self) -> None:
        """Clear all cached results."""
        self.cache.clear()


class SearchToolFactory:
    """Factory for creating search providers based on configuration."""

    @staticmethod
    async def create(provider_name: str, api_key: Optional[str] = None) -> SearchProvider:
        """Create search provider instance.

        Args:
            provider_name: Provider name (tavily or serper)
            api_key: API key for provider

        Returns:
            Initialized search provider
        """
        if provider_name == "tavily":
            return TavilySearchProvider(api_key)
        elif provider_name == "serper":
            return SerperSearchProvider(api_key)
        else:
            logger.warning(f"Unknown provider: {provider_name}, defaulting to Tavily")
            return TavilySearchProvider(api_key)

    @staticmethod
    async def get_provider(provider_name: str = "tavily") -> SearchProvider:
        """Get configured search provider.

        Args:
            provider_name: Provider name from config

        Returns:
            Configured search provider instance
        """
        import os

        if provider_name == "tavily":
            api_key = os.getenv("TAVILY_API_KEY")
            return TavilySearchProvider(api_key)
        else:
            api_key = os.getenv("SERPER_API_KEY")
            return SerperSearchProvider(api_key)


# Type hint for SearchResult import
from typing import Dict
