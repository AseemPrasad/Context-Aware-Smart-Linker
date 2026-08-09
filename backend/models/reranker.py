"""CASL ColBERT / cross-encoder reranker worker.

Re-scores the top-K candidates from the hybrid retriever to improve precision
on domain-specific technical terms. Memory is bounded by running the model
inside a single worker thread with a bounded queue, so heavy concurrent load
cannot spawn unbounded model instances.

This module is fully additive and does not touch any extension code.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any

from backend.services.retrieval_engine import Candidate


class RerankerWorker:
    """Single-model-thread reranker with a bounded work queue."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model_name = model_name
        self._model: Any = None
        self._request_queue: queue.Queue = queue.Queue(maxsize=64)
        self._result: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()
        self._started = False

    def _ensure_model(self) -> Any:
        """Load the cross-encoder model once (lazy, single instance)."""
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name, max_length=256)
        return self._model

    def _worker_loop(self) -> None:
        """Process scored candidates sequentially in a single thread."""
        model = self._ensure_model()
        while True:
            item = self._request_queue.get()
            if item is None:  # sentinel to stop
                break
            query, passages, future = item
            try:
                scores = model.predict([(query, p) for p in passages])
                with self._lock:
                    self._result[future] = scores
                future.set_result(scores)
            except Exception as exc:  # pragma: no cover - defensive
                future.set_exception(exc)
            finally:
                self._request_queue.task_done()

    def _start(self) -> None:
        if not self._started:
            threading.Thread(target=self._worker_loop, daemon=True).start()
            self._started = True

    async def rerank(
        self, query: str, candidates: list[Candidate]
    ) -> list[Candidate]:
        """Re-score candidates by query-passage relevance, desc by score."""
        if not candidates:
            return candidates

        self._start()
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        passages = [c.passage for c in candidates]

        # Bounded queue ensures we never run concurrent model instances.
        self._request_queue.put((query, passages, future))
        scores = await asyncio.wrap_future(future)

        for cand, score in zip(candidates, scores):
            cand.rrf_score = float(score)

        return sorted(candidates, key=lambda c: c.rrf_score, reverse=True)
