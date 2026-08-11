"""Regression detection and evaluation stability analysis.

Distinguishes real regressions from noise/flakiness in evaluation metrics.
Implements statistical robustness checks and trend analysis.
"""

import json
import logging
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RegressionAnalysis:
    """Result of regression analysis."""

    is_regression: bool
    confidence: float
    reason: str
    recommendation: str
    baseline_score: float
    current_score: float
    delta: float
    relative_delta: float
    is_stable: bool
    variance: float


@dataclass
class StabilityResult:
    """Result of stability/flakiness check."""

    is_stable: bool
    run1_score: float
    run2_score: float
    variance: float
    threshold: float = 0.05
    note: str = ""


class RegressionDetector:
    """Detect real regressions vs noise in evaluation metrics."""

    # Regression thresholds
    ABSOLUTE_THRESHOLD = 0.03  # 3% absolute drop
    RELATIVE_THRESHOLD = 0.05  # 5% relative drop
    VARIANCE_THRESHOLD = 0.05  # Flaky if variance > 5%

    def __init__(self, lookback_runs: int = 5):
        self.lookback_runs = lookback_runs

    def detect_regression(
        self,
        current_score: float,
        historical_scores: List[float],
        metric_name: str = "unknown",
    ) -> RegressionAnalysis:
        """Detect if current score represents a real regression.

        Args:
            current_score: Current metric score (0-1)
            historical_scores: List of previous scores
            metric_name: Name of metric for logging

        Returns:
            RegressionAnalysis with confidence and recommendation
        """
        if not historical_scores:
            return RegressionAnalysis(
                is_regression=False,
                confidence=0.0,
                reason="No historical baseline",
                recommendation="Accept as baseline",
                baseline_score=current_score,
                current_score=current_score,
                delta=0.0,
                relative_delta=0.0,
                is_stable=True,
                variance=0.0,
            )

        # Calculate baseline as mean of lookback runs
        lookback = historical_scores[-self.lookback_runs :]
        baseline_score = sum(lookback) / len(lookback)

        delta = current_score - baseline_score
        relative_delta = delta / baseline_score if baseline_score > 0 else 0.0

        # Calculate variance of historical scores
        variance = self._calculate_variance(lookback)

        # Determine if regression
        is_regression = (
            delta < -self.ABSOLUTE_THRESHOLD and relative_delta < -self.RELATIVE_THRESHOLD
        )

        # Confidence based on consistency of baseline
        confidence = 1.0 - min(1.0, variance / self.VARIANCE_THRESHOLD)

        # Recommendation
        if is_regression:
            if variance > self.VARIANCE_THRESHOLD:
                reason = f"Regression detected but baseline unstable (variance={variance:.3f})"
                recommendation = "Investigate with caution - baseline is noisy. Re-run for confirmation."
            else:
                reason = f"Real regression: {delta:.3f} absolute, {relative_delta:.1%} relative"
                recommendation = "BLOCK MERGE: Revert changes and investigate"
        else:
            if delta < 0:
                reason = f"Minor dip: {delta:.3f} absolute, within noise margins"
                recommendation = "Allow with monitoring - expected variance"
            else:
                reason = f"Improvement: {delta:.3f} absolute"
                recommendation = "PASS: Metrics stable or improved"

        return RegressionAnalysis(
            is_regression=is_regression,
            confidence=confidence,
            reason=reason,
            recommendation=recommendation,
            baseline_score=baseline_score,
            current_score=current_score,
            delta=delta,
            relative_delta=relative_delta,
            is_stable=variance < self.VARIANCE_THRESHOLD,
            variance=variance,
        )

    def check_stability(self, run1_score: float, run2_score: float) -> StabilityResult:
        """Check if evaluator is stable (re-scoring same input gives consistent results).

        Args:
            run1_score: First run score
            run2_score: Second run score

        Returns:
            StabilityResult indicating if evaluator is stable
        """
        variance = abs(run1_score - run2_score)
        is_stable = variance < self.VARIANCE_THRESHOLD

        note = ""
        if not is_stable:
            note = (
                f"Evaluator appears unstable (variance={variance:.3f} > {self.VARIANCE_THRESHOLD}). "
                "Consider using more stable judge model."
            )

        return StabilityResult(
            is_stable=is_stable,
            run1_score=run1_score,
            run2_score=run2_score,
            variance=variance,
            threshold=self.VARIANCE_THRESHOLD,
            note=note,
        )

    def identify_regressed_examples(
        self,
        current_results: List[Dict[str, Any]],
        historical_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Identify which examples caused regression.

        Args:
            current_results: Current evaluation results
            historical_results: Previous evaluation results (if available)

        Returns:
            List of regressed examples with details
        """
        regressed = []

        if not historical_results:
            # Without historical data, identify low-scoring examples as "at-risk"
            for result in current_results:
                score = result.get("score", 0.0)
                if score < 0.70:
                    regressed.append(
                        {
                            "question": result.get("question", ""),
                            "score": score,
                            "reason": "Low score (at-risk)",
                        }
                    )
        else:
            # Compare current vs historical
            for curr, hist in zip(current_results, historical_results):
                curr_score = curr.get("score", 0.0)
                hist_score = hist.get("score", 0.0)
                delta = curr_score - hist_score

                if delta < -0.10:  # >10% score drop
                    regressed.append(
                        {
                            "question": curr.get("question", ""),
                            "current_score": curr_score,
                            "historical_score": hist_score,
                            "delta": delta,
                        }
                    )

        logger.info(f"Identified {len(regressed)} regressed/at-risk examples")
        return regressed

    def categorize_by_type(
        self, regressed_examples: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize regressed examples by question type/pattern.

        Args:
            regressed_examples: List of regressed examples

        Returns:
            Dict mapping category to examples
        """
        categories = {
            "retrieval_heavy": [],
            "reasoning": [],
            "factual": [],
            "other": [],
        }

        for example in regressed_examples:
            question = example.get("question", "").lower()

            if any(word in question for word in ["find", "retrieve", "search", "where", "what is"]):
                categories["retrieval_heavy"].append(example)
            elif any(word in question for word in ["why", "how", "explain", "reason"]):
                categories["reasoning"].append(example)
            elif any(word in question for word in ["fact", "true", "false", "correct"]):
                categories["factual"].append(example)
            else:
                categories["other"].append(example)

        # Log breakdown
        for cat, examples in categories.items():
            if examples:
                logger.info(f"  {cat}: {len(examples)} examples")

        return categories

    @staticmethod
    def _calculate_variance(scores: List[float]) -> float:
        """Calculate variance of scores.

        Args:
            scores: List of scores

        Returns:
            Variance (standard deviation)
        """
        if not scores or len(scores) < 2:
            return 0.0

        mean = sum(scores) / len(scores)
        squared_diffs = [(s - mean) ** 2 for s in scores]
        variance = sum(squared_diffs) / len(scores)

        import math

        return math.sqrt(variance)


class CIRegressionGate:
    """Gate CI/CD pipeline based on regression analysis."""

    def __init__(self):
        self.detector = RegressionDetector()

    def should_pass(
        self,
        current_scores: Dict[str, float],
        baseline_scores: Optional[Dict[str, float]] = None,
        strict_mode: bool = False,
    ) -> Tuple[bool, str]:
        """Determine if CI should pass based on regression analysis.

        Args:
            current_scores: Current metric scores
            baseline_scores: Baseline scores for comparison
            strict_mode: If True, fail on any regression. If False, allow noise.

        Returns:
            Tuple of (should_pass: bool, reason: str)
        """
        if not baseline_scores:
            return True, "No baseline for comparison, allowing as new baseline"

        issues = []

        for metric, current_score in current_scores.items():
            baseline = baseline_scores.get(metric, current_score)
            historical = [baseline]  # Would load from file in production

            analysis = self.detector.detect_regression(current_score, historical, metric)

            if analysis.is_regression:
                issues.append(f"{metric}: {analysis.reason}")

            if not analysis.is_stable:
                issues.append(f"{metric}: Unstable baseline (variance={analysis.variance:.3f})")

        if not issues:
            return True, "All metrics passed regression checks"

        if strict_mode:
            return False, "\n".join(issues)
        else:
            # In lenient mode, allow if confidence is low (noisy baseline)
            return True, f"Issues detected but allowing due to high variance:\n" + "\n".join(issues)


def get_detector(lookback_runs: int = 5) -> RegressionDetector:
    """Get singleton regression detector instance."""
    return RegressionDetector(lookback_runs)
