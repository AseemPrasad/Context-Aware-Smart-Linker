"""Financial due-diligence API router.

Exposes endpoints for financial analysis, verification, and citation retrieval.
Completely isolated from general search endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from backend.billing.meter import UsageMeter, get_usage_meter
from backend.cache.semantic_cache import SemanticCache, get_semantic_cache
from backend.domains.finance.engine import DueDiligenceEngine
from backend.domains.finance.schemas import (
    FinancialAnalysisRequest,
    FinancialAnalysisResponse,
)
from backend.schemas.retrieval import SearchRequest, SearchResponse, SearchHit

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
    cache: SemanticCache = Depends(get_semantic_cache),
) -> FinancialAnalysisResponse:
    """Explains a financial or legal term in context with grounded citations, semantic caching, and credit metering."""
    # Reconcile tenant_id with authenticated state when AuthMiddleware is active
    auth_tenant = getattr(http_request.state, "tenant_id", None)
    if auth_tenant and auth_tenant != "default":
        request.tenant_id = auth_tenant

    # Check semantic cache first (O(1) exact hash match or vector distance)
    search_req_for_cache = SearchRequest(
        tenant_id=request.tenant_id,
        query=f"{request.term}::{request.surrounding_context}",
        top_k=5,
    )
    cached_hit = cache.get(search_req_for_cache)
    if cached_hit:
        # Cache hits burn 0 credits (Day 2 customer economic incentive)
        meter.deduct_credits(tenant_id=request.tenant_id, operation_cost=1, is_cache_hit=True)
        # Parse cached response
        hit_meta = cached_hit.hits[0].metadata if cached_hit.hits else {}
        return FinancialAnalysisResponse(
            term=request.term,
            executive_summary=cached_hit.hits[0].passage if cached_hit.hits else "Cached explanation",
            historical_context=hit_meta.get("historical_context"),
            risk_implications=hit_meta.get("risk_implications"),
            citations=[],
            confidence_score=0.98,
            cached=True,
        )

    # Deduct 1 credit for uncached RAG analysis
    deduction = meter.deduct_credits(tenant_id=request.tenant_id, operation_cost=1, is_cache_hit=False)
    if not deduction.allowed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=deduction.error_message or "Monthly research credits exhausted.",
        )

    response = await engine.analyze(request)

    # Populate cache asynchronously
    try:
        synth_response = SearchResponse(
            hits=[
                SearchHit(
                    document_id=f"cached_{request.term}",
                    passage=response.executive_summary,
                    score=1.0,
                    metadata={
                        "historical_context": response.historical_context or "",
                        "risk_implications": response.risk_implications or "",
                    },
                )
            ],
            total_hits=1,
            latency_ms=1.0,
            cached=True,
        )
        cache.set(search_req_for_cache, synth_response)
    except Exception:
        pass

    return response


@router.get("/health")
async def finance_health():
    """Health probe for the finance due diligence module."""
    return {"status": "ok", "module": "finance_due_diligence"}

