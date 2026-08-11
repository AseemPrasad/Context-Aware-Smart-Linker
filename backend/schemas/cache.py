"""Cache schema definitions for semantic caching layer.

Defines the contract for what gets cached, how cache keys are structured,
and metadata for cache entries.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CacheMetadata(BaseModel):
    """Metadata for a cached search result."""

    cache_key: str = Field(..., description="Hash key (MD5 of request payload).")
    query_embedding: list[float] = Field(..., description="Vector embedding of the query.")
    tenant_id: str = Field(..., description="Tenant that owns this cache entry.")
    top_k: int = Field(..., description="top_k parameter used in original search.")
    cached_at: float = Field(..., description="Unix timestamp when cached.")
    hit_count: int = Field(default=0, description="Number of times this entry was served.")


class CachedSearchPayload(BaseModel):
    """Complete payload for a cached search result."""

    metadata: CacheMetadata = Field(..., description="Cache entry metadata.")
    search_response: dict = Field(..., description="Original SearchResponse as dict.")
