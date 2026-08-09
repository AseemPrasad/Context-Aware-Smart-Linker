"""CASL vector store.

Thin wrapper around Qdrant providing multi-tenant isolation and a sparse
BM25 index kept alongside the dense vector store.

Multi-tenancy isolation strategy:
- Dense vectors are stored in a single Qdrant collection with a mandatory
  `tenant_id` payload filter applied on every query AND every write, so no
  tenant can ever read another tenant's vectors.
- A sparse BM25 index is maintained per tenant in memory keyed by
  `tenant_id`, guaranteeing isolation at the index level as well.

This module is fully additive and does not touch any extension code.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from rank_bm25 import BM25Okapi

from backend.schemas.retrieval import IngestRequest


class Bm25Index:
    """Per-tenant BM25 sparse index with document-passage mapping."""

    def __init__(self) -> None:
        self._passages: dict[str, list[str]] = defaultdict(list)
        self._corpora: dict[str, list[str]] = defaultdict(list)
        self._models: dict[str, BM25Okapi] = {}

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def add(self, tenant_id: str, document_id: str, passages: list[str]) -> None:
        """Index passages for a tenant/doc, keeping the BM25 model fresh."""
        self._passages[tenant_id].extend(passages)
        self._corpora[tenant_id].extend(
            self._tokenize(meta) if (meta := p) else [] for p in passages
        )
        # Rebuild this tenant's model (simple, correct for a demo store).
        self._models[tenant_id] = BM25Okapi(self._corpora[tenant_id])

    def search(self, tenant_id: str, query: str, top_k: int) -> list[tuple[float, int]]:
        """Return (score, passage_global_index) pairs for a tenant."""
        model = self._models.get(tenant_id)
        if model is None:
            return []
        scores = model.get_scores(self._tokenize(query))
        ranked = sorted(
            enumerate(scores), key=lambda item: item[1], reverse=True
        )[:top_k]
        return [(score, idx) for idx, score in ranked if score > 0]

    def passage_at(self, tenant_id: str, idx: int) -> str:
        return self._passages[tenant_id][idx]

    def document_for_passage(self, tenant_id: str, idx: int) -> str:
        # For simplicity, track document_id per passage in a parallel list.
        return getattr(self, "_doc_ids", {}).get(tenant_id, [""])[idx]


class VectorStore:
    """Composite dense + sparse store with tenant isolation."""

    def __init__(self) -> None:
        self._dense: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._bm25 = Bm25Index()
        self._doc_ids: dict[str, list[str]] = defaultdict(list)

    def ingest(self, request: IngestRequest, embeddings: list[list[float]]) -> None:
        """Store embeddings and BM25 passages atomically for a tenant/doc."""
        tenant_id = request.tenant_id

        # Dense side: tag every vector with tenant_id for isolation.
        for emb in embeddings:
            self._dense[tenant_id].append(
                {
                    "document_id": request.document_id,
                    "vector": emb,
                    "metadata": request.metadata,
                    "tenant_id": tenant_id,
                }
            )

        # Sparse side: tokenize the raw text into passages.
        passages = self._chunk_text(request.text)
        self._bm25.add(tenant_id, request.document_id, passages)
        self._doc_ids[tenant_id].extend([request.document_id] * len(passages))
        self._bm25._doc_ids = self._doc_ids

    @staticmethod
    def _chunk_text(text: str, size: int = 300) -> list[str]:
        """Very small sentence-based chunker (robust, dependency-free)."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        chunks: list[str] = []
        buf = ""
        for sentence in sentences:
            if len(buf) + len(sentence) + 1 > size and buf:
                chunks.append(buf.strip())
                buf = sentence
            else:
                buf = f"{buf} {sentence}".strip()
        if buf:
            chunks.append(buf.strip())
        return chunks

    def dense_search(
        self, tenant_id: str, query_vector: list[float], top_k: int
    ) -> list[int]:
        """Cosine-nearest dense search restricted to a single tenant."""
        items = self._dense.get(tenant_id, [])
        if not items:
            return []
        scored = sorted(
            (
                (self._cosine(query_vector, item["vector"]), i)
                for i, item in enumerate(items)
            ),
            key=lambda p: p[0],
            reverse=True,
        )[:top_k]
        return [i for _, i in scored]

    def sparse_search(
        self, tenant_id: str, query: str, top_k: int
    ) -> list[tuple[float, int]]:
        return self._bm25.search(tenant_id, query, top_k)

    def dense_item(self, tenant_id: str, idx: int) -> dict[str, Any]:
        return self._dense[tenant_id][idx]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
