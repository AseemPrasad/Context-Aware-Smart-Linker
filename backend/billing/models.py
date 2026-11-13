"""Billing and usage metering data models for Enterprise B2B SaaS."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class PlanTier(str, Enum):
    STARTER = "starter"         # Boutique/Solo: 500 queries/mo, 1-3 seats
    PROFESSIONAL = "professional" # Growth: 5,000 queries/mo, 10 seats
    ENTERPRISE = "enterprise"   # Institutional: Custom/Unlimited, SLA


class TenantSubscription(BaseModel):
    """SaaS customer subscription state and usage quotas."""
    tenant_id: str = Field(..., description="Unique enterprise customer ID")
    plan: PlanTier = Field(PlanTier.STARTER, description="Active subscription plan")
    seats_allocated: int = Field(5, description="Maximum provisioned browser extension seats")
    seats_active: int = Field(1, description="Currently active employee seats")
    monthly_credits_quota: int = Field(500, description="Allocated query credits per billing cycle")
    credits_used: int = Field(0, description="Credits consumed in current billing cycle")
    hard_cap_enabled: bool = Field(True, description="Strictly block requests when credits hit quota")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CreditDeductionResult(BaseModel):
    """Result of an atomic credit metering check."""
    allowed: bool
    credits_consumed: int
    credits_remaining: int
    plan: PlanTier
    error_message: Optional[str] = None


class UsageSummaryResponse(BaseModel):
    """Customer-facing telemetry summary for admin workspace."""
    tenant_id: str
    plan: PlanTier
    seats_allocated: int
    seats_active: int
    credits_quota: int
    credits_used: int
    credits_remaining: int
    percent_consumed: float

