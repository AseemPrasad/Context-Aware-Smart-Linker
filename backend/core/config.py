"""CASL backend configuration for semantic caching.

Centralizes all cache-related settings with sensible defaults.
All settings can be overridden via environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class CacheConfig:
    """Configuration for semantic caching layer."""

    # Redis connection
    redis_enabled: bool = os.getenv("REDIS_ENABLED", "false").lower() == "true"
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Semantic matching threshold (cosine distance)
    # Lower = stricter matching. 0.08 means ~99% similarity required
    similarity_threshold: float = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.08"))

    # Cache TTL in seconds (86400 = 24 hours)
    cache_ttl: int = int(os.getenv("CACHE_TTL", "86400"))

    # Maximum number of cache entries per tenant (soft limit)
    max_cache_entries_per_tenant: int = int(os.getenv("CACHE_MAX_ENTRIES", "10000"))

    # Redis connection timeout in seconds
    redis_timeout: int = int(os.getenv("REDIS_TIMEOUT", "2"))

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError(f"similarity_threshold must be in [0.0, 1.0], got {self.similarity_threshold}")

        if self.cache_ttl <= 0:
            raise ValueError(f"cache_ttl must be positive, got {self.cache_ttl}")

        if self.max_cache_entries_per_tenant <= 0:
            raise ValueError(f"max_cache_entries_per_tenant must be positive, got {self.max_cache_entries_per_tenant}")


def get_cache_config() -> CacheConfig:
    """Get the cache configuration singleton."""
    return CacheConfig()
