"""CASL semantic caching layer.

Two-tiered caching:
1. Exact hash match (MD5/SHA256 of request payload) — O(1) lookup
2. Semantic vector similarity (cosine distance) — if hash misses

Only caches search endpoint responses. Gracefully degrades if Redis unavailable.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from backend.cache.redis_client import get_redis_client
from backend.core.config import get_cache_config
from backend.core.encoder import get_encoder
from backend.schemas.retrieval import SearchRequest, SearchResponse


class SemanticCache:
    """Two-tiered semantic cache with exact hash + vector similarity fallback."""

    def __init__(self) -> None:
        self.redis = get_redis_client()
        self.config = get_cache_config()
        self._hit_count = 0
        self._miss_count = 0

    def _get_encoder(self) -> Any:
        """Get the shared encoder singleton."""
        return get_encoder().get_encoder()

    def _compute_hash(self, request: SearchRequest) -> str:
        """Compute MD5 hash of request payload for exact matching."""
        payload = {
            "tenant_id": request.tenant_id,
            "query": request.query,
            "top_k": request.top_k,
            "use_rerank": request.use_rerank,
        }
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.md5(payload_str.encode()).hexdigest()

    def _cache_key_exact(self, request: SearchRequest) -> str:
        """Redis key for exact hash match."""
        return f"casl:cache:exact:{self._compute_hash(request)}"

    def _cache_key_vector(self, tenant_id: str, index: int) -> str:
        """Redis key for vector similarity index entry."""
        return f"casl:cache:vector:{tenant_id}:{index}"

    def _cache_key_vectors_list(self, tenant_id: str) -> str:
        """Redis key for list of vector indices for a tenant."""
        return f"casl:cache:vectors:list:{tenant_id}"

    def get(self, request: SearchRequest) -> SearchResponse | None:
        """Try to get cached response. Returns None if cache miss or Redis unavailable."""
        if not self.redis.is_enabled:
            return None

        # Tier 1: Exact hash match
        exact_key = self._cache_key_exact(request)
        cached_json = self.redis.get(exact_key)

        if cached_json:
            self._hit_count += 1
            data = json.loads(cached_json)
            return SearchResponse(**data["search_response"])

        # Tier 2: Semantic vector similarity match
        cached = self._semantic_match(request)
        if cached:
            self._hit_count += 1
            return cached

        self._miss_count += 1
        return None

    def _semantic_match(self, request: SearchRequest) -> SearchResponse | None:
        """Find semantically similar cached query within threshold."""
        try:
            encoder = self._get_encoder()
            query_vec = encoder.encode([request.query])[0]
            query_vec = [float(x) for x in query_vec]

            # Get all vector indices for this tenant
            vectors_list_key = self._cache_key_vectors_list(request.tenant_id)
            vector_indices = self.redis.get(vectors_list_key)

            if not vector_indices:
                return None

            indices = json.loads(vector_indices)

            # Search through vectors to find best match
            best_distance = float("inf")
            best_cache_data = None

            for idx in indices:
                vector_key = self._cache_key_vector(request.tenant_id, idx)
                cache_data_json = self.redis.get(vector_key)

                if not cache_data_json:
                    continue

                cache_data = json.loads(cache_data_json)
                cached_vec = cache_data["embedding"]
                distance = self._cosine_distance(query_vec, cached_vec)

                if distance < best_distance:
                    best_distance = distance
                    best_cache_data = cache_data

            # Return if distance within threshold
            if best_distance <= self.config.similarity_threshold and best_cache_data:
                return SearchResponse(**best_cache_data["search_response"])

        except Exception:
            # Fail silent: any error in vector ops doesn't break the request
            pass

        return None

    def set(self, request: SearchRequest, response: SearchResponse) -> bool:
        """Asynchronously cache the search response (caller must await if needed)."""
        if not self.redis.is_enabled:
            return False

        try:
            encoder = self._get_encoder()
            query_vec = encoder.encode([request.query])[0]
            query_vec = [float(x) for x in query_vec]

            # Tier 1: Exact hash entry
            exact_key = self._cache_key_exact(request)
            payload = {
                "embedding": query_vec,
                "search_response": response.model_dump(),
                "cached_at": time.time(),
            }
            self.redis.set(exact_key, json.dumps(payload), ex=self.config.cache_ttl)

            # Tier 2: Vector similarity entry (indexed by tenant + timestamp-based index)
            timestamp_idx = int(time.time() * 1000000) % 1000000
            vector_key = self._cache_key_vector(request.tenant_id, timestamp_idx)
            self.redis.set(vector_key, json.dumps(payload), ex=self.config.cache_ttl)

            # Track vector indices for this tenant
            vectors_list_key = self._cache_key_vectors_list(request.tenant_id)
            existing = self.redis.get(vectors_list_key)
            indices = json.loads(existing) if existing else []
            indices.append(timestamp_idx)

            # Keep only recent N entries per tenant to avoid memory bloat
            indices = indices[-self.config.max_cache_entries_per_tenant :]
            self.redis.set(vectors_list_key, json.dumps(indices), ex=self.config.cache_ttl)

            return True

        except Exception:
            # Fail silent: cache write failure doesn't affect response
            return False

    @staticmethod
    def _cosine_distance(a: list[float], b: list[float]) -> float:
        """Compute cosine distance (1 - cosine similarity) between vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5

        if na == 0 or nb == 0:
            return 1.0

        similarity = dot / (na * nb)
        return 1.0 - similarity

    def get_stats(self) -> dict[str, int]:
        """Return cache hit/miss statistics."""
        return {"hits": self._hit_count, "misses": self._miss_count}


def get_semantic_cache() -> SemanticCache | None:
    """Get the semantic cache instance (or None if Redis disabled)."""
    config = get_cache_config()
    if config.redis_enabled:
        return SemanticCache()
    return None
