"""Atomic credit metering and quota enforcement engine.

Tracks query burn rates per tenant, incentivizes cache hits (0 credits),
and enforces hard caps to protect against runaway API consumption.
"""

import os
import threading
from typing import Dict, Optional
from backend.billing.models import CreditDeductionResult, PlanTier, TenantSubscription, UsageSummaryResponse


class UsageMeter:
    """Thread-safe usage meter with atomic check-and-burn concurrency lock."""

    def __init__(self, redis_client=None):
        self._lock = threading.Lock()
        self._tenants: Dict[str, TenantSubscription] = {}
        self.redis_client = redis_client

    def _get_or_create_unlocked(
        self, tenant_id: str, plan: PlanTier = PlanTier.STARTER
    ) -> TenantSubscription:
        """Internal helper without acquiring lock."""
        if tenant_id not in self._tenants:
            quota = 500 if plan == PlanTier.STARTER else (5000 if plan == PlanTier.PROFESSIONAL else 50000)
            seats = 3 if plan == PlanTier.STARTER else (10 if plan == PlanTier.PROFESSIONAL else 100)
            self._tenants[tenant_id] = TenantSubscription(
                tenant_id=tenant_id,
                plan=plan,
                seats_allocated=seats,
                seats_active=1,
                monthly_credits_quota=quota,
                credits_used=0,
                hard_cap_enabled=True,
            )
        return self._tenants[tenant_id]

    def get_or_create_tenant(
        self, tenant_id: str, plan: PlanTier = PlanTier.STARTER
    ) -> TenantSubscription:
        """Retrieves or provisions tenant subscription record."""
        with self._lock:
            return self._get_or_create_unlocked(tenant_id, plan)

    def deduct_credits(
        self, tenant_id: str, operation_cost: int = 1, is_cache_hit: bool = False
    ) -> CreditDeductionResult:
        """Atomically checks and burns credits for an operation with concurrency lock."""
        with self._lock:
            sub = self._get_or_create_unlocked(tenant_id)

            # Cache hits cost 0 credits (Day 2 economic incentive for customers)
            if is_cache_hit:
                return CreditDeductionResult(
                    allowed=True,
                    credits_consumed=0,
                    credits_remaining=sub.monthly_credits_quota - sub.credits_used,
                    plan=sub.plan,
                )

            projected_use = sub.credits_used + operation_cost

            # Check quota limit
            if sub.hard_cap_enabled and projected_use > sub.monthly_credits_quota:
                return CreditDeductionResult(
                    allowed=False,
                    credits_consumed=0,
                    credits_remaining=max(0, sub.monthly_credits_quota - sub.credits_used),
                    plan=sub.plan,
                    error_message=f"Monthly credit quota exceeded ({sub.credits_used}/{sub.monthly_credits_quota}). Please upgrade plan."
                )

            sub.credits_used = projected_use
            remaining = max(0, sub.monthly_credits_quota - sub.credits_used)

            return CreditDeductionResult(
                allowed=True,
                credits_consumed=operation_cost,
                credits_remaining=remaining,
                plan=sub.plan,
            )

    def get_usage_summary(self, tenant_id: str) -> UsageSummaryResponse:
        """Returns customer usage analytics for billing dashboard."""
        sub = self.get_or_create_tenant(tenant_id)
        percent = round((sub.credits_used / max(1, sub.monthly_credits_quota)) * 100, 1)
        remaining = max(0, sub.monthly_credits_quota - sub.credits_used)

        return UsageSummaryResponse(
            tenant_id=sub.tenant_id,
            plan=sub.plan,
            seats_allocated=sub.seats_allocated,
            seats_active=sub.seats_active,
            credits_quota=sub.monthly_credits_quota,
            credits_used=sub.credits_used,
            credits_remaining=remaining,
            percent_consumed=percent,
        )


_usage_meter = UsageMeter()


def get_usage_meter() -> UsageMeter:
    return _usage_meter

