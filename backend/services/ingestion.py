"""CASL chunking service.

Responsible for splitting raw document text into passages and producing
dense embeddings for the vector store. The embedder is loaded lazily to keep
startup fast and to avoid heavy model memory usage when unused.

This module is fully additive and does not touch any extension code.
"""

from __future__ import annotations

import re
from typing import Any

from backend.db.vector_store import VectorStore
from backend.schemas.retrieval import IngestRequest


class ChunkingService:
    """Chunks text into overlapping passages and embeds each passage."""

    def __init__(self, chunk_size: int = 300, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._encoder: Any = None

    def _load_encoder(self) -> Any:
        """Lazy-load the sentence-transformer encoder once."""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer(
                "all-MiniLM-L6-v2", device="cpu"
            )
        return self._encoder

    def chunk(self, text: str) -> list[str]:
        """Split text into fixed-size overlapping passages."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        passages: list[str] = []
        buf = ""
        for sentence in sentences:
            if len(buf) + len(sentence) + 1 > self.chunk_size and buf:
                passages.append(buf.strip())
                # Keep a small overlap from the end of the previous buffer.
                tail = buf.split()[-self.overlap :] if buf else []
                buf = " ".join(tail + sentence.split())
            else:
                buf = f"{buf} {sentence}".strip()
        if buf:
            passages.append(buf.strip())
        return [p for p in passages if p]

    def embed(self, passages: list[str]) -> list[list[float]]:
        """Embed passages into dense vectors."""
        if not passages:
            return []
        encoder = self._load_encoder()
        vectors = encoder.encode(passages, convert_to_numpy=True)
        return [list(map(float, v)) for v in vectors]


class IngestionService:
    """Coordinates chunking + embedding + vector store writes."""

    def __init__(
        self, store: VectorStore, chunker: ChunkingService | None = None
    ) -> None:
        self.store = store
        self.chunker = chunker or ChunkingService()

    def ingest(self, request: IngestRequest) -> int:
        """Ingest a document atomically into dense + sparse stores."""
        passages = self.chunker.chunk(request.text)
        embeddings = self.chunker.embed(passages)
        # Upsert into both stores in one call so dense/sparse stay in sync.
        self.store.ingest(request, embeddings)
        return len(passages)
