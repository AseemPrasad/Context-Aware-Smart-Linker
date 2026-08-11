"""Cache health monitoring and graceful degradation tracking.

Monitors cache availability, hit/miss rates, and allows graceful fallback
if Redis becomes unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from backend.cache.redis_client import get_redis_client
from backend.core.config import get_cache_config


@dataclass
class CacheStats:
    """Cache performance and health statistics."""

    hits: int = 0
    misses: int = 0
    redis_errors: int = 0
    encoding_errors: int = 0
    last_error: str | None = None
    last_error_time: datetime | None = None
    is_redis_connected: bool = True
    uptime_seconds: float = 0.0

    def hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def to_dict(self) -> dict:
        """Convert stats to dictionary for API responses."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(self.hit_rate(), 2),
            "redis_errors": self.redis_errors,
            "encoding_errors": self.encoding_errors,
            "is_redis_connected": self.is_redis_connected,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
        }


class CacheHealthMonitor:
    """Tracks cache health and availability for graceful degradation."""

    _instance: CacheHealthMonitor | None = None
    _stats: CacheStats = field(default_factory=CacheStats)

    def __new__(cls) -> CacheHealthMonitor:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._stats = CacheStats()
        return cls._instance

    def record_hit(self) -> None:
        """Record a cache hit."""
        self._stats.hits += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        self._stats.misses += 1

    def record_redis_error(self, error_msg: str) -> None:
        """Record a Redis connectivity error."""
        self._stats.redis_errors += 1
        self._stats.last_error = f"Redis: {error_msg}"
        self._stats.last_error_time = datetime.utcnow()
        self._stats.is_redis_connected = False

    def record_encoding_error(self, error_msg: str) -> None:
        """Record an encoding/embedding error."""
        self._stats.encoding_errors += 1
        self._stats.last_error = f"Encoding: {error_msg}"
        self._stats.last_error_time = datetime.utcnow()

    def mark_redis_healthy(self) -> None:
        """Mark Redis as healthy after recovery."""
        self._stats.is_redis_connected = True

    def check_redis_health(self) -> bool:
        """Check if Redis is currently healthy."""
        redis = get_redis_client()
        config = get_cache_config()

        if not config.redis_enabled:
            return False

        if redis.is_enabled:
            self.mark_redis_healthy()
            return True
        else:
            self.record_redis_error("Connection unavailable")
            return False

    def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset statistics (useful for testing)."""
        self._stats = CacheStats()


def get_cache_monitor() -> CacheHealthMonitor:
    """Get the cache health monitor singleton."""
    return CacheHealthMonitor()
