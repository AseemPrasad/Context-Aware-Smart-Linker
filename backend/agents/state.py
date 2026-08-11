"""Shared state machine and data structures for multi-agent context verification."""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of verifying a single fact."""

    fact: str
    source_reference: str  # Where it appears in original
    is_verified: bool
    confidence: float  # 0-1 score
    source_url: Optional[str] = None
    supporting_snippet: Optional[str] = None
    conflicting_evidence: Optional[str] = None
    verified_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class SearchResult:
    """Result from external search."""

    title: str
    url: str
    snippet: str
    confidence: Optional[float] = None


@dataclass
class AgentState:
    """Shared state across all agent nodes in the graph."""

    # Input/output
    input_context: str
    tenant_id: str = "default"

    # Planning phase
    search_queries: List[str] = field(default_factory=list)

    # Searching phase
    search_results: List[SearchResult] = field(default_factory=list)

    # Verification phase
    verification_report: List[VerificationResult] = field(default_factory=list)

    # Execution tracking
    iteration_count: int = 0
    max_iterations: int = 3
    last_routing_key: str = "START"

    # Conversation history for tracing
    messages: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    execution_start_time: Optional[float] = None
    execution_end_time: Optional[float] = None

    @property
    def execution_time_ms(self) -> float:
        """Get execution time in milliseconds."""
        if self.execution_start_time and self.execution_end_time:
            return (self.execution_end_time - self.execution_start_time) * 1000
        return 0.0

    @property
    def verification_coverage(self) -> float:
        """Get percentage of facts verified."""
        if not self.verification_report:
            return 0.0
        verified = sum(1 for v in self.verification_report if v.is_verified)
        return verified / len(self.verification_report)

    def add_message(self, role: str, content: str) -> None:
        """Add message to conversation history."""
        self.messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


class AgentConfig:
    """Configuration for multi-agent context engine."""

    def __init__(self):
        self.enabled = os.getenv("AGENTS_ENABLED", "false").lower() == "true"
        self.max_retries = int(os.getenv("AGENTS_MAX_RETRIES", "3"))
        self.timeout_seconds = int(os.getenv("AGENTS_TIMEOUT_SECONDS", "30"))
        self.search_provider = os.getenv("AGENTS_SEARCH_PROVIDER", "tavily")
        self.cache_search_results = os.getenv("AGENTS_CACHE_SEARCH_RESULTS", "true").lower() == "true"
        self.streaming_enabled = os.getenv("AGENTS_STREAMING_ENABLED", "false").lower() == "true"

        # Search API keys
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self.serper_api_key = os.getenv("SERPER_API_KEY", "")

        # Performance thresholds
        self.max_search_queries = 5
        self.max_search_results_per_query = 5
        self.search_timeout_seconds = 5

        # Verification thresholds
        self.verification_confidence_threshold = 0.6  # 60% confidence minimum
        self.verification_pass_threshold = 0.8  # 80% facts verified to pass

        logger.info(
            f"AgentConfig initialized (enabled={self.enabled}, "
            f"max_retries={self.max_retries}, search_provider={self.search_provider})"
        )


class NoOpAgent:
    """No-op agent stub for when agents are disabled."""

    async def execute(self, context: str) -> AgentState:
        """Return empty state if agents disabled."""
        return AgentState(input_context=context)


def get_agent_config() -> AgentConfig:
    """Get singleton agent configuration."""
    return AgentConfig()
