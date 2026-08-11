"""Adapter for running existing retrieval engine against evaluation datasets.

Wraps HybridRetriever and RerankerWorker in read-only mode for evaluation.
No modifications to production retrieval code.
"""

import logging
import asyncio
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result of retrieval for evaluation."""

    question: str
    retrieved_passages: List[str]
    retrieval_score: float = 0.0
    reranked: bool = False
    rerank_scores: List[float] = None


class RetrievalAdapter:
    """Wraps existing HybridRetriever and RerankerWorker for evaluation."""

    def __init__(self, top_k: int = 5, use_rerank: bool = True):
        self.top_k = top_k
        self.use_rerank = use_rerank
        self.retriever = None
        self.reranker = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialize retriever and reranker."""
        if self._initialized:
            return

        try:
            from backend.services.retrieval_engine import HybridRetriever
            from backend.models.reranker import RerankerWorker
            from backend.db.vector_store import VectorStore

            store = VectorStore()
            self.retriever = HybridRetriever(store=store)
            self.reranker = RerankerWorker()
            self._initialized = True
            logger.info("Retrieval adapter initialized")

        except ImportError as e:
            logger.error(f"Failed to import backend components: {e}")
            self._initialized = False

    async def evaluate_question(
        self, question: str, ground_truth_context: str, tenant_id: str = "default"
    ) -> RetrievalResult:
        """Retrieve passages for a question and return result.

        Args:
            question: Question to retrieve for
            ground_truth_context: Ground truth context (for comparison, not used in retrieval)
            tenant_id: Tenant ID for multi-tenant support

        Returns:
            RetrievalResult with passages and scores
        """
        self._ensure_initialized()

        if not self.retriever:
            logger.warning("Retriever not initialized, returning empty result")
            return RetrievalResult(question=question, retrieved_passages=[])

        try:
            # Create SearchRequest
            from backend.schemas.retrieval import SearchRequest

            request = SearchRequest(
                tenant_id=tenant_id,
                query=question,
                top_k=self.top_k,
                use_rerank=self.use_rerank,
            )

            # Execute retrieval
            candidates = await self.retriever.retrieve(request, top_k=self.top_k)

            # Extract passages
            passages = [c.passage for c in candidates]

            # Optionally rerank
            rerank_scores = []
            if self.use_rerank and self.reranker:
                candidates = await self.reranker.rerank(question, candidates)
                passages = [c.passage for c in candidates]
                rerank_scores = [c.rrf_score for c in candidates]

            return RetrievalResult(
                question=question,
                retrieved_passages=passages,
                reranked=self.use_rerank,
                rerank_scores=rerank_scores if rerank_scores else None,
            )

        except Exception as e:
            logger.error(f"Error retrieving for question '{question}': {e}")
            return RetrievalResult(
                question=question,
                retrieved_passages=[],
                reranked=False,
            )

    async def batch_evaluate(
        self, questions: List[str], contexts: List[str], tenant_id: str = "default"
    ) -> tuple[List[RetrievalResult], dict]:
        """Retrieve passages for multiple questions.

        Args:
            questions: List of questions
            contexts: List of ground truth contexts
            tenant_id: Tenant ID

        Returns:
            Tuple of (results list, aggregated stats dict)
        """
        results = []
        successful = 0
        failed = 0

        logger.info(f"Starting batch evaluation: {len(questions)} questions")

        for i, (question, context) in enumerate(zip(questions, contexts)):
            try:
                result = await asyncio.wait_for(
                    self.evaluate_question(question, context, tenant_id), timeout=30
                )
                results.append(result)
                successful += 1

                if (i + 1) % 10 == 0:
                    logger.info(f"Evaluated {i + 1}/{len(questions)} questions")

            except asyncio.TimeoutError:
                logger.warning(f"Timeout for question: {question[:50]}...")
                results.append(RetrievalResult(question=question, retrieved_passages=[]))
                failed += 1

            except Exception as e:
                logger.error(f"Error evaluating question '{question}': {e}")
                results.append(RetrievalResult(question=question, retrieved_passages=[]))
                failed += 1

        stats = {
            "total": len(questions),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(questions) if questions else 0.0,
            "avg_passages_retrieved": sum(
                len(r.retrieved_passages) for r in results
            ) / len(results) if results else 0,
        }

        logger.info(f"Batch evaluation complete: {stats['successful']}/{stats['total']} successful")

        return results, stats


def get_adapter(top_k: int = 5, use_rerank: bool = True) -> RetrievalAdapter:
    """Get singleton retrieval adapter instance."""
    return RetrievalAdapter(top_k=top_k, use_rerank=use_rerank)
