"""Safety mechanisms and monitoring for agent execution."""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


@dataclass
class ExecutionMetrics:
    """Metrics for a single agent execution."""

    execution_id: str
    tenant_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    iterations: int = 0
    final_coverage: float = 0.0
    latency_ms: float = 0.0
    success: bool = False
    error_message: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        """Get execution duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0


class LoopDetector:
    """Detect infinite loops in state machine execution."""

    def __init__(self, max_repeats: int = 3):
        self.max_repeats = max_repeats
        self.state_history = deque(maxlen=10)

    def check_infinite_loop(self, state: AgentState) -> bool:
        """Check if execution is stuck in infinite loop.

        Args:
            state: Current agent state

        Returns:
            True if infinite loop detected
        """
        # Create state signature (what phase we're in)
        signature = (state.iteration_count, state.last_routing_key, len(state.search_results))

        self.state_history.append(signature)

        # Check if same state repeated too many times
        if len(self.state_history) >= self.max_repeats:
            last_n = list(self.state_history)[-self.max_repeats :]
            if all(s == last_n[0] for s in last_n):
                logger.warning(f"Infinite loop detected: {last_n[0]} repeated {self.max_repeats}x")
                return True

        return False


class SearchQualityGate:
    """Prevent retries when search quality is insufficient."""

    def __init__(self, min_results_threshold: int = 2, max_empty_retries: int = 2):
        self.min_results_threshold = min_results_threshold
        self.max_empty_retries = max_empty_retries
        self.empty_search_count = 0

    def should_continue_retrying(self, state: AgentState) -> bool:
        """Determine if retrying will help or is futile.

        Args:
            state: Current agent state

        Returns:
            True if should continue, False if should stop retrying
        """
        # Track empty searches
        if len(state.search_results) < self.min_results_threshold:
            self.empty_search_count += 1

            if self.empty_search_count >= self.max_empty_retries:
                logger.warning(
                    f"Search quality insufficient after {self.max_empty_retries} attempts, "
                    f"stopping retries"
                )
                return False
        else:
            self.empty_search_count = 0  # Reset on successful search

        return True


class LLMOutputValidator:
    """Validate LLM agent outputs for correctness."""

    @staticmethod
    def validate_planner_output(search_queries: List[str], max_queries: int = 5) -> tuple[bool, Optional[str]]:
        """Validate planner output (search queries).

        Args:
            search_queries: Generated search queries
            max_queries: Maximum allowed queries

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not search_queries:
            return False, "Planner generated no search queries"

        if len(search_queries) > max_queries:
            return False, f"Too many queries: {len(search_queries)} > {max_queries}"

        for query in search_queries:
            if not isinstance(query, str) or len(query) < 3:
                return False, f"Invalid query format: {query}"

        return True, None

    @staticmethod
    def validate_verifier_output(
        verification_report: List[Any],
        original_context: str,
    ) -> tuple[bool, Optional[str]]:
        """Validate verifier output (verification report).

        Args:
            verification_report: Verification results
            original_context: Original input context

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not verification_report:
            return False, "Verifier generated no verification results"

        for result in verification_report:
            # Check fact references original context
            if hasattr(result, "fact"):
                if not any(word in original_context.lower() for word in result.fact.lower().split()):
                    return False, f"Fact does not reference original context: {result.fact}"

            # Check confidence in range
            if hasattr(result, "confidence"):
                if not (0.0 <= result.confidence <= 1.0):
                    return False, f"Invalid confidence: {result.confidence}"

        return True, None


class AgentMonitor:
    """Monitor agent executions and collect metrics."""

    def __init__(self, max_history: int = 100):
        self.metrics_history = deque(maxlen=max_history)
        self.error_count = 0
        self.success_count = 0
        self.total_latency_ms = 0.0

    def record_execution(self, metrics: ExecutionMetrics) -> None:
        """Record metrics for an execution.

        Args:
            metrics: ExecutionMetrics to record
        """
        self.metrics_history.append(metrics)

        if metrics.success:
            self.success_count += 1
        else:
            self.error_count += 1

        self.total_latency_ms += metrics.duration_ms

        logger.info(
            f"Recorded execution: {metrics.execution_id}, "
            f"success={metrics.success}, "
            f"latency={metrics.duration_ms:.1f}ms"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics from execution history.

        Returns:
            Statistics dictionary
        """
        if not self.metrics_history:
            return {"total_executions": 0}

        total = len(self.metrics_history)
        success_rate = self.success_count / total if total > 0 else 0.0
        avg_latency = self.total_latency_ms / total if total > 0 else 0.0

        # Coverage statistics
        coverages = [m.final_coverage for m in self.metrics_history if m.success]
        avg_coverage = sum(coverages) / len(coverages) if coverages else 0.0

        # Latency percentiles
        latencies = sorted([m.duration_ms for m in self.metrics_history])
        p50 = latencies[len(latencies) // 2] if latencies else 0.0
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

        return {
            "total_executions": total,
            "successful": self.success_count,
            "failed": self.error_count,
            "success_rate": round(success_rate, 2),
            "avg_latency_ms": round(avg_latency, 1),
            "median_latency_ms": round(p50, 1),
            "p95_latency_ms": round(p95, 1),
            "avg_coverage": round(avg_coverage, 2),
        }

    def check_health(self) -> tuple[bool, Optional[str]]:
        """Check overall health based on recent executions.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        stats = self.get_stats()

        if stats.get("total_executions", 0) == 0:
            return True, "No executions yet"

        success_rate = stats.get("success_rate", 0.0)
        if success_rate < 0.5:
            return False, f"Low success rate: {success_rate:.1%}"

        avg_latency = stats.get("avg_latency_ms", 0.0)
        if avg_latency > 30000:  # 30s
            return False, f"High latency: {avg_latency:.1f}ms"

        return True, "Healthy"


class SafetyGuardian:
    """Unified safety guardian combining all safety mechanisms."""

    def __init__(self):
        self.loop_detector = LoopDetector()
        self.quality_gate = SearchQualityGate()
        self.output_validator = LLMOutputValidator()
        self.monitor = AgentMonitor()

    def check_before_retry(self, state: AgentState) -> tuple[bool, Optional[str]]:
        """Check if it's safe to retry before next iteration.

        Args:
            state: Current agent state

        Returns:
            Tuple of (should_retry, reason_if_no)
        """
        # Check for infinite loops
        if self.loop_detector.check_infinite_loop(state):
            return False, "Infinite loop detected"

        # Check search quality
        if not self.quality_gate.should_continue_retrying(state):
            return False, "Search quality insufficient"

        return True, None

    def validate_outputs(self, state: AgentState) -> tuple[bool, Optional[str]]:
        """Validate all agent outputs.

        Args:
            state: Agent state to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate planner output
        is_valid, error = self.output_validator.validate_planner_output(state.search_queries)
        if not is_valid:
            return False, f"Planner output invalid: {error}"

        # Validate verifier output
        is_valid, error = self.output_validator.validate_verifier_output(
            state.verification_report, state.input_context
        )
        if not is_valid:
            return False, f"Verifier output invalid: {error}"

        return True, None


def get_monitor() -> AgentMonitor:
    """Get singleton agent monitor."""
    return AgentMonitor()


def get_guardian() -> SafetyGuardian:
    """Get singleton safety guardian."""
    return SafetyGuardian()
