"""Complexity analysis and cost calculation for intelligent routing.

Analyzes request complexity to determine appropriate model tier.
Tracks spending and enforces budget limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ComplexityLevel(str, Enum):
    """Request complexity level."""

    SIMPLE = "simple"          # 0.0-0.3: keyword lookup, quick answers
    MEDIUM = "medium"          # 0.3-0.7: synthesis, summarization
    COMPLEX = "complex"        # 0.7-1.0: multi-doc analysis, reasoning


@dataclass
class ComplexityAnalysis:
    """Analysis of request complexity."""

    complexity_score: float  # 0.0-1.0
    level: ComplexityLevel
    estimated_tokens: int
    recommended_model: str
    factors: dict[str, float]  # breakdown of factors


class ComplexityAnalyzer:
    """Analyzes request complexity for routing decisions."""

    # Simple requests -> Haiku/GPT-4o-mini
    # Medium requests -> Sonnet/GPT-4o
    # Complex requests -> Opus/GPT-4o-Turbo

    def analyze(
        self,
        query: str,
        context: str = "",
        num_hits: int = 0,
        use_rerank: bool = False,
    ) -> ComplexityAnalysis:
        """Analyze request complexity.

        Args:
            query: The search query/prompt
            context: Surrounding context or additional text
            num_hits: Number of search results to synthesize
            use_rerank: Whether reranking is needed

        Returns:
            ComplexityAnalysis with score and recommendations
        """
        factors: dict[str, float] = {}

        # Factor 1: Context length (0.0-0.3)
        total_length = len(query) + len(context)
        if total_length < 500:
            length_factor = 0.05
        elif total_length < 2000:
            length_factor = 0.15
        elif total_length < 5000:
            length_factor = 0.25
        else:
            length_factor = 0.30
        factors["context_length"] = length_factor

        # Factor 2: Query complexity (0.0-0.25)
        query_factor = self._analyze_query_complexity(query)
        factors["query_complexity"] = query_factor

        # Factor 3: Number of hits to synthesize (0.0-0.25)
        hits_factor = min(0.25, (num_hits * 0.05))
        factors["num_hits"] = hits_factor

        # Factor 4: Reranking required (0.0-0.15)
        rerank_factor = 0.15 if use_rerank else 0.0
        factors["reranking"] = rerank_factor

        # Factor 5: Keyword density (0.0-0.05)
        keyword_factor = self._analyze_keyword_density(query)
        factors["keyword_density"] = keyword_factor

        # Aggregate score
        complexity_score = sum(factors.values())
        complexity_score = min(1.0, complexity_score)  # Cap at 1.0

        # Determine level
        if complexity_score < 0.3:
            level = ComplexityLevel.SIMPLE
        elif complexity_score < 0.7:
            level = ComplexityLevel.MEDIUM
        else:
            level = ComplexityLevel.COMPLEX

        # Estimate tokens (rough heuristic)
        estimated_tokens = self._estimate_tokens(
            query, context, num_hits, complexity_score
        )

        # Recommend model based on complexity
        recommended_model = self._recommend_model(level)

        return ComplexityAnalysis(
            complexity_score=round(complexity_score, 2),
            level=level,
            estimated_tokens=estimated_tokens,
            recommended_model=recommended_model,
            factors=factors,
        )

    def _analyze_query_complexity(self, query: str) -> float:
        """Analyze query complexity based on keywords and structure."""
        # Count question words and complex operators
        complex_keywords = [
            "compare", "contrast", "analyze", "summarize", "synthesize",
            "explain", "why", "how", "complex", "relationship",
        ]
        operator_count = sum(1 for kw in complex_keywords if kw in query.lower())

        if operator_count == 0:
            return 0.05
        elif operator_count == 1:
            return 0.12
        else:
            return min(0.25, 0.12 + (operator_count - 1) * 0.05)

    def _analyze_keyword_density(self, query: str) -> float:
        """Analyze keyword density (simple lookups have high density)."""
        words = query.lower().split()
        if len(words) < 3:
            return 0.05  # Very simple query
        else:
            return 0.02  # More natural query

    def _estimate_tokens(
        self,
        query: str,
        context: str,
        num_hits: int,
        complexity_score: float,
    ) -> int:
        """Estimate token usage for the request."""
        # Rough estimate: 1 token per 4 characters
        query_tokens = len(query) // 4
        context_tokens = len(context) // 4
        hits_tokens = num_hits * 50  # ~50 tokens per hit

        # Multiply by complexity factor (more complex = longer response)
        response_multiplier = 1.0 + (complexity_score * 2.0)

        total_estimate = int((query_tokens + context_tokens + hits_tokens) * response_multiplier)
        return max(100, min(4000, total_estimate))  # Clamp between 100-4000

    def _recommend_model(self, level: ComplexityLevel) -> str:
        """Recommend model tier based on complexity."""
        if level == ComplexityLevel.SIMPLE:
            return "haiku"  # Use Haiku/GPT-4o-mini
        elif level == ComplexityLevel.MEDIUM:
            return "sonnet"  # Use Sonnet/GPT-4o
        else:
            return "opus"  # Use Opus/GPT-4o-Turbo


class CostCalculator:
    """Calculates and tracks token costs across providers."""

    def __init__(self) -> None:
        """Initialize cost calculator."""
        self.total_spend_usd = 0.0
        self.spend_by_provider: dict[str, float] = {}
        self.monthly_budget_usd: float = 100.0

    def set_monthly_budget(self, budget_usd: float) -> None:
        """Set monthly budget limit."""
        self.monthly_budget_usd = budget_usd

    def add_spend(self, provider_name: str, cost_usd: float) -> None:
        """Record spending for a provider."""
        self.total_spend_usd += cost_usd
        self.spend_by_provider[provider_name] = self.spend_by_provider.get(provider_name, 0.0) + cost_usd

    def get_remaining_budget(self) -> float:
        """Get remaining budget."""
        return max(0.0, self.monthly_budget_usd - self.total_spend_usd)

    def is_budget_exceeded(self) -> bool:
        """Check if budget has been exceeded."""
        return self.total_spend_usd > self.monthly_budget_usd

    def get_usage_percent(self) -> float:
        """Get budget usage as percentage."""
        if self.monthly_budget_usd == 0:
            return 0.0
        return (self.total_spend_usd / self.monthly_budget_usd) * 100.0

    def should_warn(self) -> tuple[bool, str]:
        """Check if budget warning threshold exceeded."""
        usage_percent = self.get_usage_percent()

        if usage_percent >= 100.0:
            return True, f"Budget exceeded! Used ${self.total_spend_usd:.2f} of ${self.monthly_budget_usd:.2f}"
        elif usage_percent >= 95.0:
            remaining = self.get_remaining_budget()
            return True, f"WARNING: 95% of budget used. ${remaining:.2f} remaining"
        elif usage_percent >= 80.0:
            remaining = self.get_remaining_budget()
            return True, f"INFO: 80% of budget used. ${remaining:.2f} remaining"

        return False, ""

    def reset_monthly(self) -> None:
        """Reset monthly spend tracking."""
        self.total_spend_usd = 0.0
        self.spend_by_provider = {}

    def get_stats(self) -> dict[str, Any]:
        """Get cost statistics."""
        return {
            "total_spend": round(self.total_spend_usd, 2),
            "monthly_budget": self.monthly_budget_usd,
            "remaining": round(self.get_remaining_budget(), 2),
            "usage_percent": round(self.get_usage_percent(), 1),
            "spend_by_provider": {k: round(v, 2) for k, v in self.spend_by_provider.items()},
        }


def get_complexity_analyzer() -> ComplexityAnalyzer:
    """Get complexity analyzer instance."""
    return ComplexityAnalyzer()


def get_cost_calculator() -> CostCalculator:
    """Get cost calculator singleton."""
    if not hasattr(get_cost_calculator, "_instance"):
        get_cost_calculator._instance = CostCalculator()
    return get_cost_calculator._instance
