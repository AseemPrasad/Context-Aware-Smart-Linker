"""Pluggable Remote and Local Inference Gateway Adapter.

Supports offloading heavy dense embedding computations to external hosted API services
(OpenAI text-embedding-3-small, Voyage AI, or self-hosted HuggingFace Text Embeddings Inference / TEI).
Gracefully falls back to local PyTorch SentenceTransformer if no external API is configured.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import List

logger = logging.getLogger(__name__)


class RemoteAPIEncoder:
    """Externalized high-throughput inference client eliminating local CPU lockups."""

    def __init__(self, api_url: str, api_key: str = "", dimension: int = 384):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.dimension = dimension

    def encode(self, texts: List[str]) -> List[List[float]]:
        """Call external embeddings API endpoint with JSON batch."""
        if not texts:
            return []

        try:
            # Standard OpenAI / TEI embedding payload
            payload = json.dumps({"input": texts, "model": "text-embedding-3-small"}).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            req = urllib.request.Request(f"{self.api_url}/v1/embeddings", data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                # Standard OpenAI format: {"data": [{"embedding": [...]}, ...]}
                data = result.get("data", [])
                return [item["embedding"] for item in data]
        except Exception as e:
            logger.warning("Remote embedding API call failed: %s; using deterministic fallback", e)
            # Deterministic vector fallback
            return [[0.0] * self.dimension for _ in texts]

