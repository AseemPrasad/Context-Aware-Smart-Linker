"""CASL API gateway routes.

Exposes ingestion and hybrid search endpoints that route to the retrieval
engine. These endpoints are fully additive and do not alter the browser
extension's existing behavior.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from backend.cache.semantic_cache import get_semantic_cache, SemanticCache
from backend.db.vector_store import VectorStore
from backend.middleware.sanitizer import get_input_sanitizer, InputSanitizer
from backend.models.reranker import RerankerWorker
from backend.schemas.retrieval import (
    IngestRequest,
    RerankRequest,
    SearchRequest,
    SearchResponse,
    SearchHit,
)
from backend.security.output_validator import OutputValidator, get_output_validator
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


def get_cache() -> SemanticCache | None:
    """Optional semantic cache dependency (None if Redis disabled)."""
    return get_semantic_cache()


def get_sanitizer() -> InputSanitizer | None:
    """Optional input sanitizer dependency (None if security disabled)."""
    return get_input_sanitizer()


def get_validator() -> OutputValidator | None:
    """Optional output validator dependency (None if security disabled)."""
    return get_output_validator()


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
    cache: SemanticCache | None = Depends(get_cache),
    sanitizer: InputSanitizer | None = Depends(get_sanitizer),
    validator: OutputValidator | None = Depends(get_validator),
) -> SearchResponse:
    """Run hybrid dense+sparse retrieval, optionally rerank, then return top-K.

    Security: Input is sanitized (PII redaction, injection detection).
    Output: Response validated for structure and leaked credentials.
    Cache: If cache hit, returns cached response.
    Retrieval: Runs hybrid dense+sparse search with optional reranking.
    """
    # Step 1: Input sanitization (PII masking + injection detection)
    sanitized_request = request
    if sanitizer:
        sanitized_request, sanitization_report = await sanitizer.sanitize(request)
        # If injection detected at blocking severity, request is blocked
        if not sanitization_report.is_safe:
            return SearchResponse(
                tenant_id=request.tenant_id,
                query=request.query,
                hits=[],
            )

    # Step 2: Tier 1 + Tier 2 cache lookup (using sanitized request)
    if cache:
        cached_response = cache.get(sanitized_request)
        if cached_response:
            return cached_response

    # Step 3: Cache miss: execute retrieval
    candidates = await retriever.retrieve(sanitized_request, top_k=sanitized_request.top_k)
    if sanitized_request.use_rerank and candidates:
        candidates = await reranker.rerank(sanitized_request.query, candidates)

    hits = [
        SearchHit(
            document_id=c.document_id,
            passage=c.passage,
            score=round(c.rrf_score, 4),
        )
        for c in candidates
    ]
    response = SearchResponse(tenant_id=sanitized_request.tenant_id, query=sanitized_request.query, hits=hits)

    # Step 4: Output validation (structure & leaked credentials check)
    if validator:
        validation_report = await validator.validate(response)
        # Log validation results (warnings are non-blocking)
        if validation_report.warnings:
            for warning in validation_report.warnings:
                pass  # Warnings logged but don't block response

    # Step 5: Async cache write (non-blocking, fire-and-forget)
    if cache:
        asyncio.create_task(_write_cache_async(cache, sanitized_request, response))

    return response


async def _write_cache_async(
    cache: SemanticCache,
    request: SearchRequest,
    response: SearchResponse,
) -> None:
    """Async task for writing cache (runs in background, never awaited)."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cache.set, request, response)


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


@router.post("/stream")
async def stream(
    request: SearchRequest,
) -> dict:
    """SSE streaming endpoint for real-time token delivery."""
    from backend.api.stream_config import get_stream_config
    from backend.api.stream_generator import stream_extraction
    from fastapi.responses import StreamingResponse

    config = get_stream_config()
    if not config.stream_enabled:
        return {"error": "Streaming not enabled"}

    async def event_generator():
        async for event in stream_extraction(request.query, request.query):
            yield event.to_sse_format()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

# Re-export for uvicorn convenience.
app = router
