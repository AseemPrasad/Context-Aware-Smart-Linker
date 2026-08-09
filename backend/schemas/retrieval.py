"""CASL retrieval schemas.

Pydantic models that define the contract between the browser extension,
the API gateway, and the retrieval engine. All models are additive and do
not depend on any existing extension code.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TenantContext(BaseModel):
    """Identifies the tenant that owns a document or query."""

    tenant_id: str = Field(..., description="Unique identifier of the tenant.")


class IngestRequest(BaseModel):
    """Request to ingest a document for a given tenant."""

    tenant_id: str = Field(..., description="Tenant that owns this document.")
    document_id: str = Field(..., description="Client-supplied document id.")
    text: str = Field(..., description="Raw document text to chunk and index.")
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Optional document metadata."
    )


class SearchRequest(BaseModel):
    """Request to run a hybrid hybrid search for a tenant."""

    tenant_id: str = Field(..., description="Tenant scope for the search.")
    query: str = Field(..., description="The user query text.")
    top_k: int = Field(50, ge=1, le=200, description="Candidates to rerank.")
    use_rerank: bool = Field(True, description="Whether to apply ColBERT reranking.")


class RerankRequest(BaseModel):
    """Request to rerank a set of candidate passages."""

    query: str = Field(..., description="The original query.")
    passages: list[str] = Field(..., description="Candidate passages to re-score.")


class SearchHit(BaseModel):
    """A single ranked passage result."""

    document_id: str = Field(..., description="Source document id.")
    passage: str = Field(..., description="The passage text.")
    score: float = Field(..., description="Final fused / reranked score.")


class SearchResponse(BaseModel):
    """Response returned to the client with the top-K context payload."""

    tenant_id: str = Field(..., description="Tenant the search was scoped to.")
    query: str = Field(..., description="Echo of the query.")
    hits: list[SearchHit] = Field(
        default_factory=list, description="Ranked context passages."
    )
