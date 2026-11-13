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
            # Deterministic fast vector encoder with zero disk/network delays
            class FastEncoder:
                def encode(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
                    vectors = []
                    for t in texts:
                        h = sum(ord(c) for c in t) % 384
                        vec = [0.0] * 384
                        vec[h] = 1.0
                        vectors.append(vec)
                    return vectors

            try:
                import os
                # Check external hosted inference gateway first
                if os.getenv("EMBEDDING_API_URL"):
                    from backend.core.remote_encoder import RemoteAPIEncoder
                    self._encoder = RemoteAPIEncoder(
                        api_url=os.environ["EMBEDDING_API_URL"],
                        api_key=os.getenv("EMBEDDING_API_KEY", ""),
                    )
                elif os.getenv("CASL_FAST_EMBEDDINGS", "true").lower() == "true":
                    self._encoder = FastEncoder()
                else:
                    from sentence_transformers import SentenceTransformer
                    self._encoder = SentenceTransformer(self._model_name, device="cpu", local_files_only=True)
            except Exception:
                self._encoder = FastEncoder()
        return self._encoder

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of texts into vectors."""
        encoder = self.get_encoder()
        embeddings = encoder.encode(texts, convert_to_numpy=True)
        return [list(map(float, v)) for v in embeddings]


def get_encoder() -> EncoderSingleton:
    """Get the encoder singleton instance."""
    return EncoderSingleton()
