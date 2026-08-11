"""LLM-powered agent node implementations for the context verification graph."""

import logging
import asyncio
from typing import List, Optional

from backend.agents.state import AgentState, AgentConfig, SearchResult, VerificationResult

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Deconstructs context into structured search queries."""

    def __init__(self, config: AgentConfig):
        self.config = config

    async def plan(self, state: AgentState) -> AgentState:
        """Generate search queries from input context.

        Args:
            state: Current agent state

        Returns:
            Updated state with search_queries populated
        """
        if not state.input_context:
            logger.warning("No input context provided to planner")
            state.add_message("planner", "No context to plan")
            return state

        # Simulate LLM planning (in production, would call actual LLM)
        # For now, extract key noun phrases as queries
        queries = self._extract_queries(state.input_context)

        state.search_queries = queries[:self.config.max_search_queries]
        state.add_message("planner", f"Generated {len(state.search_queries)} search queries")

        logger.info(f"Planner generated {len(state.search_queries)} queries for tenant {state.tenant_id}")

        return state

    def _extract_queries(self, context: str) -> List[str]:
        """Extract key phrases as search queries (placeholder implementation).

        Args:
            context: Input context text

        Returns:
            List of search queries
        """
        # Simple heuristic: extract sentences with key indicators
        queries = []

        sentences = context.split(".")
        for sentence in sentences[:self.config.max_search_queries]:
            sentence = sentence.strip()
            if len(sentence) > 10:
                # Take first sentence as-is (would be better with NLP)
                queries.append(sentence)

        if not queries:
            # Fallback: use first N words as query
            words = context.split()[:10]
            queries.append(" ".join(words))

        return queries


class SearcherAgent:
    """Fetches live external references via search APIs."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.provider = None

    async def search(self, state: AgentState) -> AgentState:
        """Execute searches for all queries in parallel.

        Args:
            state: Current agent state with search_queries

        Returns:
            Updated state with search_results populated
        """
        if not state.search_queries:
            logger.warning("No search queries provided to searcher")
            state.add_message("searcher", "No queries to search")
            return state

        # Execute searches in parallel with timeout
        tasks = [
            asyncio.wait_for(self._search_query(query), timeout=self.config.search_timeout_seconds)
            for query in state.search_queries
        ]

        try:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            # Flatten results and handle exceptions
            all_results = []
            for results in results_list:
                if isinstance(results, Exception):
                    logger.warning(f"Search failed: {results}")
                    continue
                if results:
                    all_results.extend(results)

            state.search_results = all_results[: self.config.max_search_results_per_query * len(state.search_queries)]
            state.add_message("searcher", f"Retrieved {len(state.search_results)} results")

            logger.info(
                f"Searcher found {len(state.search_results)} results "
                f"from {len(state.search_queries)} queries for tenant {state.tenant_id}"
            )

        except asyncio.TimeoutError:
            logger.warning(f"Search timeout for tenant {state.tenant_id}")
            state.add_message("searcher", "Search timeout")

        return state

    async def _search_query(self, query: str) -> List[SearchResult]:
        """Execute single search query.

        Args:
            query: Search query string

        Returns:
            List of search results
        """
        # Placeholder: would call actual search provider
        # In production, would route to Tavily/Serper based on config
        try:
            results = [
                SearchResult(
                    title=f"Result for '{query}'",
                    url=f"https://example.com/result-{hash(query) % 1000}",
                    snippet=f"This is a search result snippet for query: {query}",
                    confidence=0.8,
                )
            ]
            return results

        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return []


class VerifierAgent:
    """Cross-checks facts against search results to prevent hallucinations."""

    def __init__(self, config: AgentConfig):
        self.config = config

    async def verify(self, state: AgentState) -> AgentState:
        """Verify facts from input context against search results.

        Args:
            state: Current agent state with input_context and search_results

        Returns:
            Updated state with verification_report and routing decision
        """
        if not state.search_results:
            logger.warning("No search results to verify against")
            state.add_message("verifier", "No search results for verification")
            state.last_routing_key = "REPLAN"
            return state

        # Extract sentences from context as facts
        facts = [s.strip() for s in state.input_context.split(".") if s.strip()]

        # Verify each fact
        report = []
        for fact in facts[:10]:  # Limit to 10 facts for performance
            verification = await self._verify_fact(fact, state.search_results)
            report.append(verification)

        state.verification_report = report

        # Determine routing
        coverage = state.verification_coverage
        if coverage >= self.config.verification_pass_threshold:
            state.last_routing_key = "VERIFIED"
            state.add_message("verifier", f"Verification passed ({coverage:.1%} coverage)")
        else:
            if state.iteration_count < state.max_iterations:
                state.last_routing_key = "REPLAN"
                state.add_message("verifier", f"Low coverage ({coverage:.1%}), replanning")
            else:
                state.last_routing_key = "VERIFIED"
                state.add_message("verifier", f"Max retries reached, forcing pass ({coverage:.1%})")

        logger.info(
            f"Verifier checked {len(report)} facts, "
            f"coverage={coverage:.1%}, routing={state.last_routing_key}"
        )

        return state

    async def _verify_fact(self, fact: str, search_results: List[SearchResult]) -> VerificationResult:
        """Verify single fact against search results.

        Args:
            fact: Fact to verify
            search_results: Search results to verify against

        Returns:
            VerificationResult with confidence score
        """
        if not fact or not search_results:
            return VerificationResult(
                fact=fact,
                source_reference="",
                is_verified=False,
                confidence=0.0,
            )

        # Simple heuristic: check word overlap with search snippets
        fact_words = set(fact.lower().split())
        max_overlap = 0.0
        best_url = None
        best_snippet = None

        for result in search_results:
            snippet_words = set(result.snippet.lower().split())
            overlap = len(fact_words & snippet_words) / len(fact_words) if fact_words else 0

            if overlap > max_overlap:
                max_overlap = overlap
                best_url = result.url
                best_snippet = result.snippet

        # Determine verification based on overlap
        is_verified = max_overlap > 0.5  # >50% word overlap = verified
        confidence = min(1.0, max_overlap * 1.2)  # Boost confidence slightly

        return VerificationResult(
            fact=fact,
            source_reference="original_context",
            is_verified=is_verified,
            confidence=confidence,
            source_url=best_url,
            supporting_snippet=best_snippet,
        )


async def planner_node(state: AgentState) -> AgentState:
    """LangGraph node: Planning phase."""
    config = AgentConfig()
    agent = PlannerAgent(config)
    return await agent.plan(state)


async def searcher_node(state: AgentState) -> AgentState:
    """LangGraph node: Searching phase."""
    config = AgentConfig()
    agent = SearcherAgent(config)
    return await agent.search(state)


async def verifier_node(state: AgentState) -> AgentState:
    """LangGraph node: Verification phase."""
    config = AgentConfig()
    agent = VerifierAgent(config)
    return await agent.verify(state)


def routing_decision(state: AgentState) -> str:
    """Determine next node based on verifier output.

    Args:
        state: Current agent state

    Returns:
        Routing key: "VERIFIED" or "REPLAN"
    """
    return state.last_routing_key
