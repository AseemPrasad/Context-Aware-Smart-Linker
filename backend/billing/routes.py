"""B2B SaaS customer portal and usage telemetry API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from backend.billing.meter import UsageMeter, get_usage_meter
from backend.billing.models import PlanTier, UsageSummaryResponse

router = APIRouter(prefix="/api/v1/billing", tags=["SaaS Billing & Usage"])


@router.get("/usage/{tenant_id}", response_model=UsageSummaryResponse)
async def get_tenant_usage(
    tenant_id: str,
    meter: UsageMeter = Depends(get_usage_meter)
) -> UsageSummaryResponse:
    """Returns current query consumption, remaining credits, and active seats."""
    return meter.get_usage_summary(tenant_id)


@router.post("/upgrade/{tenant_id}")
async def upgrade_plan(
    tenant_id: str,
    target_plan: PlanTier,
    meter: UsageMeter = Depends(get_usage_meter)
) -> dict:
    """Upgrades enterprise tenant tier and expands quota allocations."""
    sub = meter.get_or_create_tenant(tenant_id)
    sub.plan = target_plan
    if target_plan == PlanTier.PROFESSIONAL:
        sub.monthly_credits_quota = 5000
        sub.seats_allocated = 10
    elif target_plan == PlanTier.ENTERPRISE:
        sub.monthly_credits_quota = 50000
        sub.seats_allocated = 100

    return {
        "status": "upgraded",
        "tenant_id": tenant_id,
        "new_plan": sub.plan,
        "new_quota": sub.monthly_credits_quota,
        "seats_allocated": sub.seats_allocated,
    }

