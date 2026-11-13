"""Stripe B2B Subscription and Webhook Automation Router.

Handles incoming Stripe webhook events for self-serve upgrades, renewals,
and subscription cancellations, automatically synchronizing tenant quotas.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request, status

from backend.billing.models import PlanTier
from backend.billing.meter import get_usage_meter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing/stripe", tags=["Stripe Billing"])

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


@router.post("/webhook")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
) -> Dict[str, Any]:
    """Ingests Stripe lifecycle webhook events and updates tenant quotas."""
    body_bytes = await request.body()
    
    if not STRIPE_WEBHOOK_SECRET:
        # Development / test mode
        try:
            event = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            return {"status": "ignored", "reason": "invalid_json"}
    else:
        try:
            import stripe
            event = stripe.Webhook.construct_event(
                payload=body_bytes,
                sig_header=stripe_signature,
                secret=STRIPE_WEBHOOK_SECRET
            )
        except Exception as e:
            logger.warning("Stripe signature validation failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Webhook signature verification failed: {e}"
            )

    event_type = event.get("type", "")
    data_obj = event.get("data", {}).get("object", {})
    meter = get_usage_meter()

    if event_type == "checkout.session.completed":
        # New subscription purchased
        client_ref = data_obj.get("client_reference_id") or data_obj.get("metadata", {}).get("tenant_id")
        plan_name = data_obj.get("metadata", {}).get("plan", "professional").lower()
        if client_ref:
            plan = PlanTier.ENTERPRISE if "enterprise" in plan_name else PlanTier.PROFESSIONAL
            meter.get_or_create_tenant(client_ref, plan=plan)
            logger.info("Upgraded tenant %s to %s via Stripe checkout", client_ref, plan.value)

    elif event_type == "invoice.paid":
        # Monthly renewal successful
        customer_id = data_obj.get("customer")
        lines = data_obj.get("lines", {}).get("data", [])
        tenant_id = data_obj.get("subscription_details", {}).get("metadata", {}).get("tenant_id")
        if tenant_id:
            logger.info("Renewed billing period for tenant %s via Stripe invoice.paid", tenant_id)

    elif event_type in ["customer.subscription.deleted", "customer.subscription.paused"]:
        # Downgrade on cancellation
        tenant_id = data_obj.get("metadata", {}).get("tenant_id")
        if tenant_id:
            meter.get_or_create_tenant(tenant_id, plan=PlanTier.STARTER)
            logger.info("Downgraded tenant %s to STARTER upon subscription cancellation", tenant_id)

    return {"status": "processed", "event_type": event_type}

