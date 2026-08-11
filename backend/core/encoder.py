"""Shared encoder singleton for sentence embeddings.

Both the retrieval engine and semantic cache use sentence-transformers.
This module provides a singleton encoder instance to avoid loading the model
multiple times and to share embeddings across the application.

The encoder is lazy-loaded on first use to keep startup fast.
"""

from __future__ import annotations

from typing import Any


class EncoderSingleton:
    """Lazy-loaded sentence-transformer encoder singleton."""

    _instance: EncoderSingleton | None = None
    _encoder: Any = None
    _model_name: str = "all-MiniLM-L6-v2"

    def __new__(cls) -> EncoderSingleton:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_encoder(self) -> Any:
        """Get or load the encoder (lazy initialization)."""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self._model_name, device="cpu")
        return self._encoder

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of texts into vectors."""
        encoder = self.get_encoder()
        embeddings = encoder.encode(texts, convert_to_numpy=True)
        return [list(map(float, v)) for v in embeddings]


def get_encoder() -> EncoderSingleton:
    """Get the encoder singleton instance."""
    return EncoderSingleton()
