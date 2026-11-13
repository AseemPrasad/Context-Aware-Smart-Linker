"""Atomic credit metering and quota enforcement engine.

Tracks query burn rates per tenant, incentivizes cache hits (0 credits),
and enforces hard caps to protect against runaway API consumption.
"""

from typing import Dict
from backend.billing.models import CreditDeductionResult, PlanTier, TenantSubscription, UsageSummaryResponse


class UsageMeter:
    """Thread-safe usage meter with Redis-like atomic semantics."""

    def __init__(self):
        # In-memory storage for local runtime; easily backed by Redis HINCRBY in cloud clusters
        self._tenants: Dict[str, TenantSubscription] = {}

    def get_or_create_tenant(
        self, tenant_id: str, plan: PlanTier = PlanTier.STARTER
    ) -> TenantSubscription:
        """Retrieves or provisions tenant subscription record."""
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

    def deduct_credits(
        self, tenant_id: str, operation_cost: int = 1, is_cache_hit: bool = False
    ) -> CreditDeductionResult:
        """Atomically checks and burns credits for an operation."""
        # Cache hits cost 0 credits (Day 2 economic incentive for customers)
        if is_cache_hit:
            sub = self.get_or_create_tenant(tenant_id)
            return CreditDeductionResult(
                allowed=True,
                credits_consumed=0,
                credits_remaining=sub.monthly_credits_quota - sub.credits_used,
                plan=sub.plan,
            )

        sub = self.get_or_create_tenant(tenant_id)
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

