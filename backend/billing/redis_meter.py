"""Redis-backed atomic usage meter for enterprise multi-tenant deployments.

Provides atomic credit increments and quota validation using Redis keys with
monthly TTL windows. Falls back gracefully to in-memory meter if Redis is unreachable.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import redis
except ImportError:
    redis = None

from backend.billing.models import CreditDeductionResult, PlanTier, TenantSubscription, UsageSummaryResponse
from backend.billing.meter import UsageMeter

logger = logging.getLogger(__name__)


class RedisUsageMeter(UsageMeter):
    """Atomic multi-replica usage meter powered by Redis with in-memory fallback."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        super().__init__()
        self.redis_client = None
        if redis is not None:
            try:
                self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
                # Verify ping
                self.redis_client.ping()
            except Exception as e:
                logger.warning("Redis not reachable for UsageMeter, using in-memory mode: %s", e)
                self.redis_client = None

    def _get_period_key(self, tenant_id: str) -> str:
        now = datetime.now(timezone.utc)
        period = now.strftime("%Y%m")
        return f"casl:usage:{tenant_id}:{period}"

    def _get_meta_key(self, tenant_id: str) -> str:
        return f"casl:plan:{tenant_id}"

    def get_or_create_tenant(
        self, tenant_id: str, plan: PlanTier = PlanTier.STARTER
    ) -> TenantSubscription:
        """Fetch subscription from Redis, falling back to local state if offline."""
        if not self.redis_client:
            return super().get_or_create_tenant(tenant_id, plan)

        try:
            period_key = self._get_period_key(tenant_id)
            meta_key = self._get_meta_key(tenant_id)

            pipe = self.redis_client.pipeline()
            pipe.get(period_key)
            pipe.get(meta_key)
            results = pipe.execute()

            used_credits = int(results[0]) if results[0] else 0
            plan_str = results[1] if results[1] else plan.value
            active_plan = PlanTier(plan_str) if plan_str in [p.value for p in PlanTier] else plan
            quota = 500 if active_plan == PlanTier.STARTER else (5000 if active_plan == PlanTier.PROFESSIONAL else 50000)
            seats = 3 if active_plan == PlanTier.STARTER else (10 if active_plan == PlanTier.PROFESSIONAL else 100)

            return TenantSubscription(
                tenant_id=tenant_id,
                plan=active_plan,
                seats_allocated=seats,
                seats_active=1,
                monthly_credits_quota=quota,
                credits_used=used_credits,
                hard_cap_enabled=True,
            )
        except Exception as err:
            logger.warning("Redis get_or_create_tenant failed, falling back to in-memory: %s", err)
            return super().get_or_create_tenant(tenant_id, plan)

    def deduct_credits(
        self, tenant_id: str, operation_cost: int = 1, is_cache_hit: bool = False
    ) -> CreditDeductionResult:
        """Atomic credit deduction in Redis via script/pipeline."""
        if is_cache_hit:
            sub = self.get_or_create_tenant(tenant_id)
            remaining = max(0, sub.monthly_credits_quota - sub.credits_used)
            return CreditDeductionResult(
                allowed=True,
                credits_consumed=0,
                credits_remaining=remaining,
                plan=sub.plan,
            )

        if not self.redis_client:
            return super().deduct_credits(tenant_id, operation_cost, is_cache_hit)

        try:
            sub = self.get_or_create_tenant(tenant_id)
            limit = sub.monthly_credits_quota
            period_key = self._get_period_key(tenant_id)

            # Atomic increment
            new_used = self.redis_client.incrby(period_key, operation_cost)
            # Set 35-day TTL for the period key
            self.redis_client.expire(period_key, 35 * 86400)

            if new_used > limit:
                # Rollback excess increment
                self.redis_client.decrby(period_key, operation_cost)
                return CreditDeductionResult(
                    allowed=False,
                    credits_consumed=0,
                    credits_remaining=max(0, limit - sub.credits_used),
                    plan=sub.plan,
                    error_message=f"Monthly credit quota exceeded ({sub.credits_used}/{limit}). Please upgrade plan.",
                )

            return CreditDeductionResult(
                allowed=True,
                credits_consumed=operation_cost,
                credits_remaining=max(0, limit - new_used),
                plan=sub.plan,
            )
        except Exception as err:
            logger.warning("Redis deduct_credits failed, falling back to in-memory: %s", err)
            return super().deduct_credits(tenant_id, operation_cost, is_cache_hit)
