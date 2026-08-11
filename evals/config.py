"""Evaluation configuration with cost control and sampling strategies.

Defines pricing models, sampling tiers, and cost estimation.
All costs are estimated based on LLM judge model selection.
"""

import os
import logging
from typing import Dict, Literal

logger = logging.getLogger(__name__)


class CostEstimator:
    """Estimate evaluation costs based on configuration."""

    # Per-call pricing for different models (USD)
    MODEL_PRICING = {
        "ollama:local": {"per_call": 0.0, "name": "Local Ollama (Free)"},
        "openai:gpt-3.5-turbo": {"per_call": 0.001, "name": "GPT-3.5 Turbo ($0.001/call)"},
        "openai:gpt-4": {"per_call": 0.03, "name": "GPT-4 ($0.03/call)"},
    }

    @staticmethod
    def estimate_run_cost(
        dataset_size: int,
        metrics_count: int = 4,  # faithfulness, relevance, precision, recall
        judge_model: str = "ollama:local",
    ) -> float:
        """Estimate cost for a single evaluation run.

        Args:
            dataset_size: Number of samples to evaluate
            metrics_count: Number of metrics to compute
            judge_model: Judge model to use

        Returns:
            Estimated cost in USD
        """
        pricing = CostEstimator.MODEL_PRICING.get(judge_model, {"per_call": 0.0})
        cost_per_call = pricing["per_call"]

        # Each sample requires metrics_count evaluations
        total_calls = dataset_size * metrics_count
        total_cost = total_calls * cost_per_call

        return total_cost

    @staticmethod
    def breakdown_by_tier(judge_model: str = "ollama:local") -> Dict[str, Dict]:
        """Get cost breakdown for each evaluation tier.

        Args:
            judge_model: Judge model to use

        Returns:
            Dict with cost info for each tier
        """
        return {
            "tier_1_pr_check": {
                "name": "PR Check (Fast)",
                "dataset_size": 20,
                "metrics": 4,
                "estimated_cost": CostEstimator.estimate_run_cost(20, 4, judge_model),
                "estimated_time": "1-2 minutes",
            },
            "tier_2_main_merge": {
                "name": "Main Branch Merge",
                "dataset_size": 50,
                "metrics": 4,
                "estimated_cost": CostEstimator.estimate_run_cost(50, 4, judge_model),
                "estimated_time": "3-5 minutes",
            },
            "tier_3_release": {
                "name": "Release Validation",
                "dataset_size": 100,
                "metrics": 4,
                "estimated_cost": CostEstimator.estimate_run_cost(100, 4, judge_model),
                "estimated_time": "8-12 minutes",
            },
            "tier_4_full": {
                "name": "Full Evaluation",
                "dataset_size": 500,
                "metrics": 4,
                "estimated_cost": CostEstimator.estimate_run_cost(500, 4, judge_model),
                "estimated_time": "40-60 minutes",
            },
        }


class SamplingStrategy:
    """Define sampling strategies for different evaluation tiers."""

    # Tier definitions
    TIERS = {
        "pr_check": {
            "dataset_size": 20,
            "judge_model": "ollama:local",
            "timeout_seconds": 60,
            "metrics_subset": ["faithfulness", "relevance"],
            "use_cache": True,
        },
        "main_merge": {
            "dataset_size": 50,
            "judge_model": "ollama:local",
            "timeout_seconds": 180,
            "metrics_subset": ["faithfulness", "relevance", "precision"],
            "use_cache": True,
        },
        "release": {
            "dataset_size": 100,
            "judge_model": "ollama:local",
            "timeout_seconds": 600,
            "metrics_subset": ["faithfulness", "relevance", "precision", "recall"],
            "use_cache": False,
        },
        "full": {
            "dataset_size": 500,
            "judge_model": "openai:gpt-3.5-turbo",
            "timeout_seconds": 3600,
            "metrics_subset": ["faithfulness", "relevance", "precision", "recall"],
            "use_cache": False,
        },
    }

    @staticmethod
    def get_tier_config(tier: str) -> Dict:
        """Get configuration for evaluation tier.

        Args:
            tier: Tier name (pr_check, main_merge, release, full)

        Returns:
            Tier configuration dict
        """
        if tier not in SamplingStrategy.TIERS:
            logger.warning(f"Unknown tier: {tier}, using pr_check")
            tier = "pr_check"

        return SamplingStrategy.TIERS[tier]

    @staticmethod
    def recommend_tier(context: str) -> str:
        """Recommend evaluation tier based on context.

        Args:
            context: Context ('pr', 'main', 'release', 'manual')

        Returns:
            Recommended tier name
        """
        mapping = {
            "pr": "pr_check",
            "main": "main_merge",
            "release": "release",
            "manual": "full",
        }
        return mapping.get(context, "pr_check")


class EvaluationConfigAdvanced:
    """Extended evaluation configuration with cost and sampling control."""

    def __init__(self):
        # Basic settings
        self.enabled = os.getenv("EVALS_ENABLED", "false").lower() == "true"
        self.fast_mode = os.getenv("EVAL_FAST_MODE", "true").lower() == "true"
        self.cache_scores = os.getenv("EVAL_CACHE_SCORES", "true").lower() == "true"

        # Sampling configuration
        self.sample_size = int(os.getenv("EVAL_SAMPLE_SIZE", "20"))
        self.judge_model = os.getenv("EVAL_JUDGE_MODEL", "ollama:local")
        self.timeout_seconds = int(os.getenv("EVAL_TIMEOUT_SECONDS", "30"))

        # Cost control
        self.max_monthly_cost = float(os.getenv("EVAL_MAX_MONTHLY_COST_USD", "50.0"))
        self.cost_per_run = CostEstimator.estimate_run_cost(
            self.sample_size, judge_model=self.judge_model
        )

        # Paths
        self.dataset_dir = os.getenv("EVAL_DATASET_DIR", "evals/datasets")
        self.results_dir = os.getenv("EVAL_RESULTS_DIR", "evals/results")
        self.cache_dir = os.getenv("EVAL_CACHE_DIR", "evals/.cache")

        # Tier
        self.tier = os.getenv("EVAL_TIER", "pr_check")

        logger.info(
            f"EvaluationConfigAdvanced: "
            f"enabled={self.enabled}, "
            f"tier={self.tier}, "
            f"cost_per_run=${self.cost_per_run:.4f}, "
            f"max_monthly=${self.max_monthly_cost}"
        )

    def get_tier_config(self) -> Dict:
        """Get current tier configuration."""
        return SamplingStrategy.get_tier_config(self.tier)

    def should_run_evaluation(self) -> bool:
        """Determine if evaluation should run based on cost/config.

        Returns:
            True if evaluation should proceed
        """
        if not self.enabled:
            return False

        # Could add cost tracking logic here
        # For now, always run if enabled
        return True

    def get_cost_breakdown(self) -> str:
        """Get human-readable cost breakdown for current tier.

        Returns:
            Formatted cost summary
        """
        breakdown = CostEstimator.breakdown_by_tier(self.judge_model)
        tier_info = breakdown.get(f"tier_{self._tier_number()}_" + self.tier.split("_")[-1])

        if tier_info:
            return (
                f"Evaluation Tier: {tier_info['name']}\n"
                f"  Dataset Size: {tier_info['dataset_size']} samples\n"
                f"  Estimated Cost: ${tier_info['estimated_cost']:.4f}\n"
                f"  Estimated Time: {tier_info['estimated_time']}"
            )

        return "Unknown tier"

    def _tier_number(self) -> int:
        """Get numeric tier level for sorting."""
        tier_order = {"pr_check": 1, "main_merge": 2, "release": 3, "full": 4}
        return tier_order.get(self.tier, 1)


def print_cost_summary():
    """Print cost summary for all tiers and models."""
    print("\n" + "=" * 80)
    print("LLM EVALUATION COST SUMMARY")
    print("=" * 80 + "\n")

    for model in ["ollama:local", "openai:gpt-3.5-turbo", "openai:gpt-4"]:
        print(f"\n{CostEstimator.MODEL_PRICING[model]['name']}:")
        print("-" * 60)

        breakdown = CostEstimator.breakdown_by_tier(model)
        for tier_key, tier_info in breakdown.items():
            print(
                f"  {tier_info['name']:30} | "
                f"{tier_info['dataset_size']:3} samples | "
                f"${tier_info['estimated_cost']:7.4f} | "
                f"{tier_info['estimated_time']}"
            )

    print("\n" + "=" * 80)


if __name__ == "__main__":
    print_cost_summary()
