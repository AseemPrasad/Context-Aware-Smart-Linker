"""CASL hybrid retrieval engine.

Runs dense semantic search and sparse BM25 search in parallel, then fuses
their rankings using Reciprocal Rank Fusion (RRF) to produce an ordered list
of top-K candidates for the reranker.

This module is fully additive and does not touch any extension code.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from backend.db.vector_store import VectorStore
from backend.schemas.retrieval import SearchRequest
from backend.observability.tracer import get_tracer

RRF_K = 60  # Standard RRF constant.


@dataclass
class Candidate:
    """A fused candidate passage with provenance."""

    document_id: str
    passage: str
    rrf_score: float = 0.0
    ranks: list[int] = field(default_factory=list)


class HybridRetriever:
    """Parallel dense + sparse retriever with RRF fusion."""

    def __init__(self, store: VectorStore) -> None:
        self.store = store
        self._encoder = None

    def _load_encoder(self) -> object:
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        return self._encoder

    def _dense_rank(self, request: SearchRequest, top_k: int) -> list[int]:
        """Rank dense indices by cosine similarity for the tenant."""
        if not (items := self.store._dense.get(request.tenant_id, [])):
            return []
        encoder = self._load_encoder()
        query_vec = [float(x) for x in encoder.encode([request.query])[0]]
        return self.store.dense_search(request.tenant_id, query_vec, top_k)

    def _sparse_rank(self, request: SearchRequest, top_k: int) -> list[tuple[float, int]]:
        """Rank sparse BM25 passages for the tenant."""
        return self.store.sparse_search(request.tenant_id, request.query, top_k)

    async def retrieve(self, request: SearchRequest, top_k: int = 50) -> list[Candidate]:
        """Run dense + sparse search in parallel and fuse via RRF."""
        tracer = get_tracer()
        start_time = time.time()

        with tracer.start_as_current_span("retrieval.hybrid") as root_span:
            # Dense search
            dense_start = time.time()
            with tracer.start_as_current_span("retrieval.dense") as dense_span:
                dense_fut = asyncio.to_thread(self._dense_rank, request, top_k)
                dense_hits = await dense_fut
                dense_time = (time.time() - dense_start) * 1000
                dense_span.set_attribute("latency_ms", round(dense_time, 2))
                dense_span.set_attribute("num_results", len(dense_hits))

            # Sparse search
            sparse_start = time.time()
            with tracer.start_as_current_span("retrieval.sparse") as sparse_span:
                sparse_fut = asyncio.to_thread(self._sparse_rank, request, top_k)
                sparse_hits = await sparse_fut
                sparse_time = (time.time() - sparse_start) * 1000
                sparse_span.set_attribute("latency_ms", round(sparse_time, 2))
                sparse_span.set_attribute("num_results", len(sparse_hits))

            candidates: dict[str, Candidate] = {}

            # Dense list: each index is a tenant-dense entry.
            for rank, idx in enumerate(dense_hits, start=1):
                item = self.store.dense_item(request.tenant_id, idx)
                key = item["document_id"]
                cand = candidates.setdefault(
                    key,
                    Candidate(
                        document_id=item["document_id"],
                        passage=item.get("metadata", {}).get("passage", ""),
                    ),
                )
                cand.ranks.append(rank)
                cand.rrf_score += 1.0 / (RRF_K + rank)

            # Sparse hits: (score, passage_global_index).
            for rank, (_, idx) in enumerate(sparse_hits, start=1):
                passage = self.store._bm25.passage_at(request.tenant_id, idx)
                doc_id = self.store._doc_ids.get(request.tenant_id, [""])[idx]
                key = f"{doc_id}::{idx}"
                cand = candidates.setdefault(
                    key,
                    Candidate(document_id=doc_id, passage=passage),
                )
                cand.ranks.append(rank)
                cand.rrf_score += 1.0 / (RRF_K + rank)

            ordered = sorted(
                candidates.values(), key=lambda c: c.rrf_score, reverse=True
            )[:top_k]

            total_time = (time.time() - start_time) * 1000
            root_span.set_attribute("num_candidates", len(ordered))
            root_span.set_attribute("top_k", top_k)
            root_span.set_attribute("latency_ms", round(total_time, 2))

            return ordered
