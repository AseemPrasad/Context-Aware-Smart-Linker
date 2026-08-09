"""CASL API gateway routes.

Exposes ingestion and hybrid search endpoints that route to the retrieval
engine. These endpoints are fully additive and do not alter the browser
extension's existing behavior.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from backend.db.vector_store import VectorStore
from backend.models.reranker import RerankerWorker
from backend.schemas.retrieval import (
    IngestRequest,
    RerankRequest,
    SearchRequest,
    SearchResponse,
    SearchHit,
)
from backend.services.ingestion import IngestionService
from backend.services.retrieval_engine import HybridRetriever

router = APIRouter(prefix="/api/v1")

# Application-level singletons (kept intentionally simple).
_store = VectorStore()
_ingestion = IngestionService(store=_store)
_retriever = HybridRetriever(store=_store)
_reranker = RerankerWorker()


def get_store() -> VectorStore:
    return _store


def get_ingestion() -> IngestionService:
    return _ingestion


def get_retriever() -> HybridRetriever:
    return _retriever


def get_reranker() -> RerankerWorker:
    return _reranker


@router.post("/ingest", status_code=201)
async def ingest(
    request: IngestRequest,
    ingestion: IngestionService = Depends(get_ingestion),
) -> dict:
    """Chunk, embed, and index a document for a tenant."""
    num_passages = ingestion.ingest(request)
    return {"tenant_id": request.tenant_id, "document_id": request.document_id,
            "passages_indexed": num_passages}


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    reranker: RerankerWorker = Depends(get_reranker),
) -> SearchResponse:
    """Run hybrid dense+sparse retrieval, optionally rerank, then return top-K."""
    candidates = await retriever.retrieve(request, top_k=request.top_k)
    if request.use_rerank and candidates:
        candidates = await reranker.rerank(request.query, candidates)

    hits = [
        SearchHit(
            document_id=c.document_id,
            passage=c.passage,
            score=round(c.rrf_score, 4),
        )
        for c in candidates
    ]
    return SearchResponse(tenant_id=request.tenant_id, query=request.query, hits=hits)


@router.post("/rerank")
async def rerank(
    request: RerankRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    reranker: RerankerWorker = Depends(get_reranker),
) -> dict:
    """Rerank an arbitrary list of passages against a query."""
    loop = asyncio.get_running_loop()
    # Wrap simple strings into Candidate objects for the rerank signature.
    from backend.services.retrieval_engine import Candidate

    candidates = [
        Candidate(document_id=f"p{i}", passage=p) for i, p in enumerate(request.passages)
    ]
    ranked = await reranker.rerank(request.query, candidates)
    return {"scores": [round(c.rrf_score, 4) for c in ranked],
            "passages": [c.passage for c in ranked]}

# Re-export for uvicorn convenience.
app = router
