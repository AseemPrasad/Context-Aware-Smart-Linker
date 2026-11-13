"""Domain-specific metadata models and schemas for Financial & Regulatory Due Diligence."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FinancialCitation(BaseModel):
    """Citation linking an explanation claim to an immutable filing source."""
    source_id: str = Field(..., description="Unique document ID or hash in vector store")
    document_title: str = Field(..., description="Filing name, e.g. 'NVDA FY2024 10-K'")
    ticker: Optional[str] = Field(None, description="Stock ticker symbol, e.g. NVDA, AAPL")
    form_type: Optional[str] = Field(None, description="Form type, e.g. 10-K, 10-Q, 8-K, S-1")
    section: Optional[str] = Field(None, description="Section or Item, e.g. Item 1A, Note 12")
    excerpt: str = Field(..., description="Exact textual excerpt backing the claim")
    source_url: Optional[str] = Field(None, description="Direct URL to SEC EDGAR or source filing")


class FinancialAnalysisRequest(BaseModel):
    """Request payload for due-diligence context-aware explanations."""
    term: str = Field(..., description="Selected technical or financial term / clause / figure")
    surrounding_context: str = Field(..., description="Surrounding DOM paragraph / context")
    page_title: str = Field(..., description="Webpage or document title")
    ticker: Optional[str] = Field(None, description="Optional explicit ticker, if known")
    tenant_id: str = Field("default", description="Tenant isolation ID")
    strict_citations: bool = Field(True, description="Enforce strict grounded citations")


class FinancialAnalysisResponse(BaseModel):
    """Structured due-diligence response with provenance and citations."""
    term: str
    executive_summary: str = Field(..., description="Crisp, high-fidelity explanation of the term/clause")
    historical_context: Optional[str] = Field(None, description="Prior filing comparison or context")
    risk_implications: Optional[str] = Field(None, description="Key risks or covenant considerations")
    citations: List[FinancialCitation] = Field(default_factory=list, description="Ground-truth source citations")
    confidence_score: float = Field(0.95, description="Factual alignment confidence score")
    cached: bool = Field(False, description="Whether response was served from semantic cache")

