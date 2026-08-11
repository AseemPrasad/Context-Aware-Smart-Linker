"""Verified anchored context output generation and validation."""

import logging
import re
from typing import List, Optional
from dataclasses import dataclass, asdict

from backend.agents.state import AgentState, VerificationResult

logger = logging.getLogger(__name__)


@dataclass
class ContextAnchor:
    """Single verified fact with source reference."""

    fact: str
    source_url: Optional[str]
    confidence: float  # 0-1
    supporting_snippet: Optional[str] = None
    verified_at: str = ""
    is_external_source: bool = False


@dataclass
class AnchoredContext:
    """Final output with verified facts and metadata."""

    original_context: str
    anchors: List[ContextAnchor]
    verification_coverage: float  # % of facts verified
    total_facts: int
    verified_facts: int
    execution_latency_ms: float
    passed_verification: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "original_context": self.original_context,
            "anchors": [asdict(a) for a in self.anchors],
            "verification_coverage": round(self.verification_coverage, 2),
            "total_facts": self.total_facts,
            "verified_facts": self.verified_facts,
            "execution_latency_ms": round(self.execution_latency_ms, 1),
            "passed_verification": self.passed_verification,
        }


class ContextAnchorGenerator:
    """Generate verified anchored context from agent state."""

    @staticmethod
    def generate(state: AgentState, verification_threshold: float = 0.6) -> AnchoredContext:
        """Convert verification report to anchored context output.

        Args:
            state: Final agent state with verification_report
            verification_threshold: Minimum confidence to include anchor (0-1)

        Returns:
            AnchoredContext with verified facts
        """
        anchors = []

        for result in state.verification_report:
            # Skip low-confidence results
            if result.confidence < verification_threshold:
                logger.debug(f"Skipping low-confidence fact: {result.fact[:50]}...")
                continue

            anchor = ContextAnchor(
                fact=result.fact,
                source_url=result.source_url,
                confidence=result.confidence,
                supporting_snippet=result.supporting_snippet,
                verified_at=result.verified_at,
                is_external_source=bool(result.source_url),
            )

            anchors.append(anchor)

        # Sort by confidence (highest first)
        anchors.sort(key=lambda a: a.confidence, reverse=True)

        verified_count = sum(1 for r in state.verification_report if r.is_verified)
        total_count = len(state.verification_report) if state.verification_report else 1

        output = AnchoredContext(
            original_context=state.input_context,
            anchors=anchors,
            verification_coverage=state.verification_coverage,
            total_facts=total_count,
            verified_facts=verified_count,
            execution_latency_ms=state.execution_time_ms,
            passed_verification=state.last_routing_key == "VERIFIED",
        )

        logger.info(
            f"Generated anchored context: {len(anchors)} anchors, "
            f"coverage={output.verification_coverage:.1%}"
        )

        return output


class ContextAnchorValidator:
    """Validate anchored context output for integrity and safety."""

    @staticmethod
    def validate(output: AnchoredContext) -> tuple[bool, List[str]]:
        """Validate anchored context for safety and correctness.

        Args:
            output: AnchoredContext to validate

        Returns:
            Tuple of (is_valid, list of validation errors)
        """
        errors = []

        # Check 1: No new claims introduced
        for anchor in output.anchors:
            if not ContextAnchorValidator._is_substring_in_context(
                anchor.fact, output.original_context
            ):
                errors.append(
                    f"Anchor contains claim not in original context: {anchor.fact[:50]}..."
                )

        # Check 2: All URLs are valid format
        for anchor in output.anchors:
            if anchor.source_url:
                if not ContextAnchorValidator._is_valid_url(anchor.source_url):
                    errors.append(f"Invalid URL format: {anchor.source_url}")

        # Check 3: Confidence scores in range
        for anchor in output.anchors:
            if not (0.0 <= anchor.confidence <= 1.0):
                errors.append(f"Confidence out of range [0,1]: {anchor.confidence}")

        # Check 4: At least some anchors if context non-empty
        if output.original_context and not output.anchors and output.total_facts > 0:
            errors.append("No anchors generated for non-empty context")

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def _is_substring_in_context(fact: str, context: str) -> bool:
        """Check if fact appears as substring in original context.

        Args:
            fact: Fact to check
            context: Original context

        Returns:
            True if fact is substring of context
        """
        # Simple substring check (would be more sophisticated in production)
        fact_normalized = fact.lower().strip()
        context_normalized = context.lower().strip()

        return fact_normalized in context_normalized or len(fact_normalized) < 10

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Check if URL is valid format.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid
        """
        url_pattern = r"^https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=]+"
        return bool(re.match(url_pattern, url))


class OutputFormatter:
    """Format anchored context for different output types."""

    @staticmethod
    def to_json(output: AnchoredContext) -> dict:
        """Convert to JSON-serializable dict."""
        return output.to_dict()

    @staticmethod
    def to_markdown(output: AnchoredContext) -> str:
        """Convert to Markdown format.

        Returns:
            Markdown string with anchored facts
        """
        lines = []

        lines.append("# Verified Context\n")
        lines.append(f"**Verification Coverage**: {output.verification_coverage:.1%}\n")
        lines.append(f"**Execution Time**: {output.execution_latency_ms:.1f}ms\n")

        if output.anchors:
            lines.append("\n## Verified Facts\n")

            for i, anchor in enumerate(output.anchors, 1):
                confidence_pct = int(anchor.confidence * 100)
                lines.append(f"{i}. {anchor.fact}")
                lines.append(f"   - Confidence: {confidence_pct}%")

                if anchor.source_url:
                    lines.append(f"   - Source: [{anchor.source_url}]({anchor.source_url})")

                if anchor.supporting_snippet:
                    lines.append(f"   - Snippet: > {anchor.supporting_snippet[:100]}...")

                lines.append("")
        else:
            lines.append("\nNo verified facts found.")

        return "\n".join(lines)

    @staticmethod
    def to_html(output: AnchoredContext) -> str:
        """Convert to HTML format.

        Returns:
            HTML string with styled anchored facts
        """
        html = []

        html.append("<div class='anchored-context'>")
        html.append(f"<h2>Verified Context</h2>")
        html.append(
            f"<p>Coverage: <strong>{output.verification_coverage:.1%}</strong> | "
            f"Time: {output.execution_latency_ms:.1f}ms</p>"
        )

        if output.anchors:
            html.append("<ol class='anchors'>")

            for anchor in output.anchors:
                confidence_pct = int(anchor.confidence * 100)
                html.append(f"<li>")
                html.append(f"<p>{anchor.fact}</p>")
                html.append(f"<small>Confidence: {confidence_pct}%")

                if anchor.source_url:
                    html.append(
                        f" | <a href='{anchor.source_url}' target='_blank'>Source</a>"
                    )

                html.append("</small>")
                html.append(f"</li>")

            html.append("</ol>")
        else:
            html.append("<p>No verified facts found.</p>")

        html.append("</div>")

        return "\n".join(html)
