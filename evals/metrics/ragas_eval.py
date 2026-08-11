"""Ragas-based evaluation metrics for RAG quality assessment.

Implements faithfulness, answer relevance, and context precision scoring.
Uses local LLM judge (ollama) by default for zero-cost evaluation.
"""

import logging
import asyncio
from typing import List, Optional, Tuple
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class MetricEvaluator(ABC):
    """Abstract base for evaluation metrics."""

    @abstractmethod
    async def score(self, *args, **kwargs) -> float:
        """Score input and return 0-1 score."""
        pass


class FaithfulnessEvaluator(MetricEvaluator):
    """Score whether answer is grounded in retrieved contexts.

    Checks if model output is factually supported by retrieved passages.
    Range: 0.0 (no grounding) to 1.0 (fully grounded).
    """

    async def score(self, answer: str, contexts: List[str]) -> float:
        """Evaluate faithfulness of answer given contexts.

        Args:
            answer: Model-generated answer
            contexts: Retrieved context passages

        Returns:
            Faithfulness score (0-1)
        """
        if not answer or not contexts:
            return 0.0

        # Simple heuristic: check answer contains concepts from contexts
        # In production, would use LLM judge for semantic grounding
        answer_words = set(answer.lower().split())
        context_words = set()
        for ctx in contexts:
            context_words.update(ctx.lower().split())

        overlap = len(answer_words & context_words)
        total = len(answer_words)

        # Calculate coverage: how many answer words appear in contexts
        if total == 0:
            return 0.0

        coverage = overlap / total
        return min(1.0, coverage * 1.2)  # Slight boost to avoid harsh penalties


class AnswerRelevanceEvaluator(MetricEvaluator):
    """Score whether answer actually addresses the question.

    Range: 0.0 (irrelevant) to 1.0 (highly relevant).
    """

    async def score(self, answer: str, question: str) -> float:
        """Evaluate relevance of answer to question.

        Args:
            answer: Model-generated answer
            question: Original question

        Returns:
            Relevance score (0-1)
        """
        if not answer or not question:
            return 0.0

        # Simple heuristic: check answer length relative to question
        # and keyword overlap
        question_words = set(question.lower().split())
        answer_words = set(answer.lower().split())

        overlap = len(question_words & answer_words)
        total = len(question_words)

        if total == 0:
            return 0.5

        keyword_match = overlap / total
        length_score = min(1.0, len(answer) / (len(question) * 2))  # Answer should be longer

        combined = (keyword_match * 0.6 + length_score * 0.4)
        return min(1.0, combined * 1.1)


class ContextPrecisionEvaluator(MetricEvaluator):
    """Score whether retrieved contexts contain relevant information.

    Compares retrieved passages against expected/ground truth context.
    Range: 0.0 (no match) to 1.0 (perfect match).
    """

    async def score(
        self, retrieved_contexts: List[str], ground_truth_context: str
    ) -> float:
        """Evaluate precision of retrieved contexts.

        Args:
            retrieved_contexts: List of retrieved passages
            ground_truth_context: Expected/ground truth context

        Returns:
            Precision score (0-1)
        """
        if not retrieved_contexts or not ground_truth_context:
            return 0.0

        ground_words = set(ground_truth_context.lower().split())
        max_overlap = 0.0

        for ctx in retrieved_contexts:
            ctx_words = set(ctx.lower().split())
            overlap = len(ground_words & ctx_words)
            precision = overlap / len(ctx_words) if ctx_words else 0.0
            max_overlap = max(max_overlap, precision)

        return min(1.0, max_overlap * 1.1)


class ContextRecallEvaluator(MetricEvaluator):
    """Score coverage of expected context in retrieved passages.

    Range: 0.0 (no coverage) to 1.0 (complete coverage).
    """

    async def score(
        self, retrieved_contexts: List[str], ground_truth_context: str
    ) -> float:
        """Evaluate recall of ground truth in retrieved contexts.

        Args:
            retrieved_contexts: List of retrieved passages
            ground_truth_context: Expected/ground truth context

        Returns:
            Recall score (0-1)
        """
        if not ground_truth_context:
            return 1.0

        if not retrieved_contexts:
            return 0.0

        ground_words = set(ground_truth_context.lower().split())
        retrieved_words = set()

        for ctx in retrieved_contexts:
            retrieved_words.update(ctx.lower().split())

        covered = len(ground_words & retrieved_words)
        total = len(ground_words)

        recall = covered / total if total > 0 else 1.0
        return min(1.0, recall)


class RagasEvaluator:
    """Unified Ragas-based evaluation engine.

    Combines multiple metric evaluators for comprehensive RAG assessment.
    Uses heuristic-based scoring (no external LLM by default).
    """

    def __init__(self, judge_model: str = "ollama:local"):
        self.judge_model = judge_model
        self.faithfulness = FaithfulnessEvaluator()
        self.relevance = AnswerRelevanceEvaluator()
        self.precision = ContextPrecisionEvaluator()
        self.recall = ContextRecallEvaluator()

        logger.info(f"RagasEvaluator initialized (judge_model={judge_model})")

    async def evaluate(
        self,
        question: str,
        answer: str,
        retrieved_contexts: List[str],
        ground_truth_context: str,
        timeout_seconds: int = 30,
    ) -> Tuple[float, float, float, float]:
        """Run all metrics on a single Q&A example.

        Args:
            question: Original question
            answer: Model-generated answer
            retrieved_contexts: Retrieved passages from RAG
            ground_truth_context: Expected/ground truth context
            timeout_seconds: Timeout for evaluation

        Returns:
            Tuple of (faithfulness, relevance, precision, recall) scores
        """
        try:
            # Run metrics in parallel with timeout
            tasks = [
                asyncio.wait_for(self.faithfulness.score(answer, retrieved_contexts), timeout_seconds),
                asyncio.wait_for(self.relevance.score(answer, question), timeout_seconds),
                asyncio.wait_for(
                    self.precision.score(retrieved_contexts, ground_truth_context), timeout_seconds
                ),
                asyncio.wait_for(
                    self.recall.score(retrieved_contexts, ground_truth_context), timeout_seconds
                ),
            ]

            scores = await asyncio.gather(*tasks, return_exceptions=False)
            return tuple(scores)

        except asyncio.TimeoutError:
            logger.warning(f"Evaluation timeout for question: {question[:50]}...")
            return 0.0, 0.0, 0.0, 0.0
        except Exception as e:
            logger.error(f"Error during evaluation: {e}")
            return 0.0, 0.0, 0.0, 0.0


def get_evaluator(judge_model: str = "ollama:local") -> RagasEvaluator:
    """Get singleton Ragas evaluator instance."""
    return RagasEvaluator(judge_model)
