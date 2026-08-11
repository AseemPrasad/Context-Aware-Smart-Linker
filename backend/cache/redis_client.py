"""Redis connection management for semantic caching.

Provides singleton Redis client with optional connectivity. If Redis is
unavailable or disabled, all operations are silently skipped (fail-silent pattern).
"""

from __future__ import annotations

import os
from typing import Any

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisClient:
    """Singleton Redis connection with fail-silent pattern."""

    _instance: RedisClient | None = None
    _client: redis.Redis | None = None
    _enabled: bool = False

    def __new__(cls) -> RedisClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize Redis connection if enabled and available."""
        if not REDIS_AVAILABLE:
            self._enabled = False
            return

        enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"
        if not enabled:
            self._enabled = False
            return

        try:
            url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self._client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
            self._client.ping()
            self._enabled = True
        except Exception as e:
            self._enabled = False
            self._client = None

    @property
    def is_enabled(self) -> bool:
        """Check if Redis is connected and enabled."""
        return self._enabled and self._client is not None

    def get(self, key: str) -> str | None:
        """Get value from Redis (returns None if unavailable)."""
        if not self.is_enabled:
            return None
        try:
            return self._client.get(key)
        except Exception:
            return None

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """Set value in Redis with optional TTL."""
        if not self.is_enabled:
            return False
        try:
            self._client.set(key, value, ex=ex)
            return True
        except Exception:
            return False

    def hset(self, name: str, mapping: dict[str, Any]) -> bool:
        """Hash set for storing structured data."""
        if not self.is_enabled:
            return False
        try:
            self._client.hset(name, mapping=mapping)
            return True
        except Exception:
            return False

    def hgetall(self, name: str) -> dict[str, Any]:
        """Get all fields from a hash."""
        if not self.is_enabled:
            return {}
        try:
            return self._client.hgetall(name) or {}
        except Exception:
            return {}

    def delete(self, *keys: str) -> bool:
        """Delete keys from Redis."""
        if not self.is_enabled:
            return False
        try:
            self._client.delete(*keys)
            return True
        except Exception:
            return False

    def expire(self, key: str, seconds: int) -> bool:
        """Set TTL on a key."""
        if not self.is_enabled:
            return False
        try:
            self._client.expire(key, seconds)
            return True
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.is_enabled:
            return False
        try:
            return bool(self._client.exists(key))
        except Exception:
            return False


def get_redis_client() -> RedisClient:
    """Get the Redis client singleton."""
    return RedisClient()
