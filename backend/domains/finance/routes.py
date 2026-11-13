"""Financial due-diligence API router.

Exposes endpoints for financial analysis, verification, and citation retrieval.
Completely isolated from general search endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from backend.billing.meter import UsageMeter, get_usage_meter
from backend.domains.finance.engine import DueDiligenceEngine
from backend.domains.finance.schemas import (
    FinancialAnalysisRequest,
    FinancialAnalysisResponse,
)

router = APIRouter(prefix="/api/v1/finance", tags=["Finance Due Diligence"])

_engine = DueDiligenceEngine()


def get_due_diligence_engine() -> DueDiligenceEngine:
    return _engine


@router.post("/explain", response_model=FinancialAnalysisResponse)
async def explain_financial_term(
    request: FinancialAnalysisRequest,
    http_request: Request,
    engine: DueDiligenceEngine = Depends(get_due_diligence_engine),
    meter: UsageMeter = Depends(get_usage_meter),
) -> FinancialAnalysisResponse:
    """Explains a financial or legal term in context with grounded citations and credit metering."""
    # Reconcile tenant_id with authenticated state when AuthMiddleware is active
    auth_tenant = getattr(http_request.state, "tenant_id", None)
    if auth_tenant and auth_tenant != "default":
        request.tenant_id = auth_tenant

    # Deduct 1 credit for standard RAG analysis
    deduction = meter.deduct_credits(tenant_id=request.tenant_id, operation_cost=1)
    if not deduction.allowed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=deduction.error_message or "Monthly research credits exhausted.",
        )
    return await engine.analyze(request)


@router.get("/health")
async def finance_health():
    """Health probe for the finance due diligence module."""
    return {"status": "ok", "module": "finance_due_diligence"}

