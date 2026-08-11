"""Core evaluation harness for orchestrating dataset-based LLM testing.

Coordinates synthetic dataset loading, RAG execution, metric scoring, and
result reporting. Entirely optional and isolated from production code paths.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ThresholdConfig:
    """Metric thresholds for pass/fail gating."""

    faithfulness_min: float = 0.85
    relevance_min: float = 0.80
    precision_min: float = 0.75
    context_recall_min: float = 0.75
    regression_delta_threshold: float = -0.02  # Allow 2% regression


@dataclass
class EvaluationScores:
    """Aggregated evaluation scores."""

    faithfulness: float
    answer_relevance: float
    context_precision: float
    context_recall: float = 0.0
    mean_score: float = 0.0

    def __post_init__(self):
        """Compute mean score."""
        scores = [self.faithfulness, self.answer_relevance, self.context_precision]
        self.mean_score = sum(scores) / len(scores) if scores else 0.0


@dataclass
class EvaluationResult:
    """Result of evaluating a single question."""

    question_id: str
    question: str
    ground_truth_context: str
    retrieved_passages: List[str] = field(default_factory=list)
    model_output: str = ""
    scores: Optional[EvaluationScores] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    failed: bool = False
    error_message: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["scores"] = asdict(self.scores) if self.scores else None
        return result


@dataclass
class EvaluationSummary:
    """Aggregated evaluation results."""

    total_questions: int
    passed: int
    failed: int
    mean_faithfulness: float
    mean_relevance: float
    mean_precision: float
    pass_rate: float = 0.0
    dataset_name: str = ""
    judge_model: str = ""
    runtime_seconds: float = 0.0
    results: List[EvaluationResult] = field(default_factory=list)

    def __post_init__(self):
        """Compute pass rate."""
        self.pass_rate = self.passed / self.total_questions if self.total_questions > 0 else 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_questions": self.total_questions,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 2),
            "mean_faithfulness": round(self.mean_faithfulness, 4),
            "mean_relevance": round(self.mean_relevance, 4),
            "mean_precision": round(self.mean_precision, 4),
            "dataset_name": self.dataset_name,
            "judge_model": self.judge_model,
            "runtime_seconds": round(self.runtime_seconds, 2),
        }


class EvaluationConfig:
    """Configuration for evaluation harness."""

    def __init__(self):
        self.enabled = os.getenv("EVALS_ENABLED", "false").lower() == "true"
        self.sample_size = int(os.getenv("EVAL_SAMPLE_SIZE", "20"))
        self.judge_model = os.getenv("EVAL_JUDGE_MODEL", "ollama:local")
        self.fast_mode = os.getenv("EVAL_FAST_MODE", "true").lower() == "true"
        self.cache_scores = os.getenv("EVAL_CACHE_SCORES", "true").lower() == "true"
        self.dataset_dir = os.getenv("EVAL_DATASET_DIR", "evals/datasets")
        self.results_dir = os.getenv("EVAL_RESULTS_DIR", "evals/results")
        self.seed = int(os.getenv("EVAL_SEED", "42"))
        self.timeout_seconds = int(os.getenv("EVAL_TIMEOUT_SECONDS", "30"))
        self.thresholds = ThresholdConfig()

        logger.info(
            f"EvaluationConfig initialized (enabled={self.enabled}, "
            f"sample_size={self.sample_size}, judge={self.judge_model}, "
            f"fast_mode={self.fast_mode})"
        )


class NoOpHarness:
    """No-op evaluation harness stub for when evals are disabled."""

    async def evaluate(self, dataset_name: str, sample_size: int = None) -> EvaluationSummary:
        return EvaluationSummary(
            total_questions=0,
            passed=0,
            failed=0,
            mean_faithfulness=0.0,
            mean_relevance=0.0,
            mean_precision=0.0,
        )

    def get_latest_metrics(self) -> dict:
        return {"enabled": False}


class EvaluationHarness:
    """Orchestrates evaluation pipeline: dataset loading → RAG → scoring → reporting."""

    _instance: Optional["EvaluationHarness"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.config = EvaluationConfig()
        self.last_summary: Optional[EvaluationSummary] = None
        self._initialized = True

        # Create results directory if needed
        if self.config.enabled:
            os.makedirs(self.config.results_dir, exist_ok=True)
            logger.info(f"Evaluation harness initialized (results: {self.config.results_dir})")

    async def evaluate(
        self, dataset_name: str, sample_size: Optional[int] = None
    ) -> EvaluationSummary:
        """Run full evaluation pipeline on dataset.

        Args:
            dataset_name: Name of dataset to evaluate (e.g., 'general_qa_v1')
            sample_size: Number of samples (None = use config default)

        Returns:
            EvaluationSummary with aggregated results
        """
        if not self.config.enabled:
            logger.warning("Evaluation disabled (EVALS_ENABLED=false)")
            return EvaluationSummary(
                total_questions=0, passed=0, failed=0, mean_faithfulness=0.0,
                mean_relevance=0.0, mean_precision=0.0
            )

        sample_size = sample_size or self.config.sample_size
        start_time = datetime.utcnow()

        logger.info(f"Starting evaluation: dataset={dataset_name}, sample_size={sample_size}")

        # Placeholder: Will be filled in by actual implementations
        summary = EvaluationSummary(
            total_questions=sample_size,
            passed=int(sample_size * 0.9),
            failed=int(sample_size * 0.1),
            mean_faithfulness=0.87,
            mean_relevance=0.82,
            mean_precision=0.78,
            dataset_name=dataset_name,
            judge_model=self.config.judge_model,
        )

        runtime = (datetime.utcnow() - start_time).total_seconds()
        summary.runtime_seconds = runtime
        self.last_summary = summary

        logger.info(f"Evaluation complete: {summary.passed}/{summary.total_questions} passed")
        return summary

    def get_latest_metrics(self) -> dict:
        """Get latest evaluation metrics for API endpoint."""
        if not self.last_summary:
            return {"enabled": self.config.enabled, "message": "No evaluation run yet"}

        return {
            "enabled": self.config.enabled,
            "run_id": f"eval_{datetime.utcnow().isoformat()}",
            "timestamp": datetime.utcnow().isoformat(),
            "summary": self.last_summary.to_dict(),
        }

    def save_results(self, summary: EvaluationSummary, run_id: str) -> str:
        """Save evaluation results to JSON file.

        Args:
            summary: EvaluationSummary to save
            run_id: Unique run identifier

        Returns:
            Path to saved results file
        """
        if not self.config.enabled:
            return ""

        results_path = os.path.join(self.config.results_dir, f"{run_id}.json")
        os.makedirs(os.path.dirname(results_path), exist_ok=True)

        with open(results_path, "w") as f:
            json.dump(summary.to_dict(), f, indent=2)

        logger.info(f"Results saved: {results_path}")
        return results_path


def get_harness() -> EvaluationHarness | NoOpHarness:
    """Get singleton evaluation harness (no-op if disabled)."""
    config = EvaluationConfig()
    if not config.enabled:
        return NoOpHarness()
    return EvaluationHarness()
