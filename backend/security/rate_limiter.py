"""Redis-based token-bucket rate limiting with Lua atomicity."""

import os
import logging
from typing import Optional, Dict, Tuple
import redis

logger = logging.getLogger(__name__)


class RateLimitConfig:
    """Rate limiting configuration with tier-based limits."""

    def __init__(self):
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
        self.fail_open = os.getenv("RATE_LIMIT_FAIL_OPEN", "true").lower() == "true"
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        # Tier-based limits (requests per minute)
        self.tiers = {
            "free": 60,
            "pro": 1000,
            "enterprise": 5000,
        }

        # Override tiers from environment
        for tier, default_limit in self.tiers.items():
            env_key = f"RATE_LIMIT_TIER_{tier.upper()}"
            limit = int(os.getenv(env_key, str(default_limit)))
            self.tiers[tier] = limit

        # Custom per-tenant overrides
        self.custom_limits: Dict[str, int] = {}

        logger.info(
            f"RateLimitConfig initialized (enabled={self.enabled}, "
            f"fail_open={self.fail_open}, tiers={self.tiers})"
        )


class TokenBucket:
    """Token bucket for rate limiting."""

    def __init__(self, key: str, capacity: int):
        self.key = key
        self.capacity = capacity
        self.refill_rate = capacity / 60.0  # Tokens per second


class RateLimiter:
    """Redis-based rate limiter with Lua atomic operations."""

    LUA_SCRIPT = """
    local key_tokens = KEYS[1]
    local key_refill = KEYS[2]
    local capacity = tonumber(ARGV[1])
    local now = tonumber(ARGV[2])
    local refill_rate = tonumber(ARGV[3])

    local current_tokens = tonumber(redis.call('GET', key_tokens) or capacity)
    local last_refill = tonumber(redis.call('GET', key_refill) or now)

    -- Calculate elapsed time and refill tokens
    local elapsed = math.max(0, now - last_refill)
    local tokens_to_add = elapsed * refill_rate
    current_tokens = math.min(capacity, current_tokens + tokens_to_add)

    -- Check if token available
    if current_tokens >= 1 then
        current_tokens = current_tokens - 1
        redis.call('SET', key_tokens, tostring(current_tokens), 'EX', '86400')
        redis.call('SET', key_refill, tostring(now), 'EX', '86400')
        return {1, tostring(math.floor(current_tokens)), '0'}
    else
        -- Calculate reset time
        local reset_seconds = math.ceil((1 - current_tokens) / refill_rate)
        return {0, '0', tostring(reset_seconds)}
    end
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self.redis_client: Optional[redis.Redis] = None
        self.lua_script_sha: Optional[str] = None

        if self.config.enabled:
            try:
                self.redis_client = redis.from_url(self.config.redis_url, decode_responses=True)
                self.redis_client.ping()
                # Load Lua script
                self.lua_script_sha = self.redis_client.script_load(self.LUA_SCRIPT)
                logger.info("Redis rate limiter connected")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                if not self.config.fail_open:
                    raise
                self.redis_client = None

    def get_tier_limit(self, tenant_id: str) -> int:
        """Get rate limit for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Requests per minute limit
        """
        # Check custom override
        if tenant_id in self.config.custom_limits:
            return self.config.custom_limits[tenant_id]

        # Default to Pro tier
        return self.config.tiers.get("pro", 1000)

    async def acquire(
        self,
        tenant_id: str,
        endpoint: str,
    ) -> Tuple[bool, int, int]:
        """Acquire token for request.

        Args:
            tenant_id: Tenant identifier
            endpoint: API endpoint path

        Returns:
            Tuple of (allowed: bool, remaining_tokens: int, reset_seconds: int)
        """
        if not self.config.enabled:
            return True, 999, 0

        if not self.redis_client:
            if self.config.fail_open:
                logger.warning("Rate limiter unavailable, allowing request (fail-open)")
                return True, 999, 0
            else:
                logger.error("Rate limiter unavailable, blocking request (fail-closed)")
                return False, 0, 60

        try:
            # Create token bucket for this tenant+endpoint
            capacity = self.get_tier_limit(tenant_id)
            bucket = TokenBucket(f"ratelimit:{tenant_id}:{endpoint}", capacity)

            # Execute Lua script atomically
            result = self.redis_client.evalsha(
                self.lua_script_sha,
                2,
                f"ratelimit:{tenant_id}:{endpoint}:tokens",
                f"ratelimit:{tenant_id}:{endpoint}:refill",
                capacity,
                int(os.times()[4]),  # Current time in seconds
                bucket.refill_rate,
            )

            allowed = bool(result[0])
            remaining = int(result[1])
            reset_seconds = int(result[2])

            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for tenant={tenant_id}, "
                    f"endpoint={endpoint}, reset_in={reset_seconds}s"
                )

            return allowed, remaining, reset_seconds

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            if self.config.fail_open:
                logger.warning("Rate limiter error, allowing request (fail-open)")
                return True, 999, 0
            else:
                logger.error("Rate limiter error, blocking request (fail-closed)")
                return False, 0, 60

    def set_custom_limit(self, tenant_id: str, limit_per_minute: int) -> None:
        """Set custom rate limit for tenant.

        Args:
            tenant_id: Tenant identifier
            limit_per_minute: Requests per minute
        """
        self.config.custom_limits[tenant_id] = limit_per_minute
        logger.info(f"Set custom limit for {tenant_id}: {limit_per_minute} req/min")

    def reset(self, tenant_id: str, endpoint: str) -> None:
        """Reset rate limit for tenant+endpoint (for testing).

        Args:
            tenant_id: Tenant identifier
            endpoint: API endpoint
        """
        if not self.redis_client:
            return

        try:
            self.redis_client.delete(f"ratelimit:{tenant_id}:{endpoint}:tokens")
            self.redis_client.delete(f"ratelimit:{tenant_id}:{endpoint}:refill")
            logger.info(f"Reset rate limit for {tenant_id}:{endpoint}")
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")


def get_rate_limiter() -> RateLimiter:
    """Get singleton rate limiter."""
    return RateLimiter()
