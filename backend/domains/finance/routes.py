"""Financial due-diligence API router.

Exposes endpoints for financial analysis, verification, and citation retrieval.
Completely isolated from general search endpoints.
"""

from fastapi import APIRouter, Depends
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
    engine: DueDiligenceEngine = Depends(get_due_diligence_engine),
) -> FinancialAnalysisResponse:
    """Explains a financial or legal term in context with grounded citations."""
    return await engine.analyze(request)


@router.get("/health")
async def finance_health():
    """Health probe for the finance due diligence module."""
    return {"status": "ok", "module": "finance_due_diligence"}

