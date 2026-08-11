"""LangGraph-based multi-agent orchestration engine.

Coordinates planner, searcher, and verifier agents with state machine execution.
"""

import logging
import asyncio
import time
from typing import Optional, Dict, Any

from backend.agents.state import AgentState, AgentConfig, NoOpAgent
from backend.agents.nodes import planner_node, searcher_node, verifier_node, routing_decision

logger = logging.getLogger(__name__)


class ContextVerificationGraph:
    """LangGraph execution engine for context verification workflow."""

    _instance: Optional["ContextVerificationGraph"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.config = AgentConfig()
        self.streaming_callbacks = []
        self._initialized = True

        logger.info(
            f"ContextVerificationGraph initialized (enabled={self.config.enabled}, "
            f"timeout={self.config.timeout_seconds}s)"
        )

    async def execute(
        self,
        input_context: str,
        tenant_id: str = "default",
        timeout_seconds: Optional[int] = None,
    ) -> AgentState:
        """Execute full graph workflow with timeout protection.

        Args:
            input_context: Webpage context to verify
            tenant_id: Tenant identifier for multi-tenant isolation
            timeout_seconds: Timeout for execution (None = use config default)

        Returns:
            Final AgentState with verification results
        """
        if not self.config.enabled:
            logger.warning("Agents disabled, returning no-op state")
            return AgentState(input_context=input_context, tenant_id=tenant_id)

        timeout = timeout_seconds or self.config.timeout_seconds

        try:
            return await asyncio.wait_for(
                self._execute_graph(input_context, tenant_id),
                timeout=timeout,
            )

        except asyncio.TimeoutError:
            logger.error(f"Graph execution timeout ({timeout}s) for tenant {tenant_id}")
            return AgentState(
                input_context=input_context,
                tenant_id=tenant_id,
                last_routing_key="TIMEOUT",
            )

        except Exception as e:
            logger.error(f"Graph execution error for tenant {tenant_id}: {e}")
            return AgentState(
                input_context=input_context,
                tenant_id=tenant_id,
                last_routing_key="ERROR",
            )

    async def _execute_graph(self, input_context: str, tenant_id: str) -> AgentState:
        """Execute the state machine graph.

        Args:
            input_context: Input context
            tenant_id: Tenant ID

        Returns:
            Final state after graph execution
        """
        # Initialize state
        state = AgentState(
            input_context=input_context,
            tenant_id=tenant_id,
            max_iterations=self.config.max_retries,
        )
        state.execution_start_time = time.time()

        logger.info(f"Starting graph execution for tenant {tenant_id}")

        # Graph execution loop
        while state.iteration_count < state.max_iterations:
            logger.debug(f"Graph iteration {state.iteration_count + 1}/{state.max_iterations}")

            # Emit event: iteration start
            await self._emit_event("iteration_start", state)

            # Planning phase
            state = await self._safe_node_exec(planner_node, state, "planner")
            if not state.search_queries:
                logger.warning("Planner produced no queries, terminating")
                break

            # Searching phase
            state = await self._safe_node_exec(searcher_node, state, "searcher")
            if not state.search_results:
                logger.warning("Searcher produced no results, terminating")
                break

            # Verification phase
            state = await self._safe_node_exec(verifier_node, state, "verifier")

            # Emit event: iteration complete
            await self._emit_event("iteration_complete", state)

            # Routing decision
            routing = routing_decision(state)
            logger.debug(f"Routing decision: {routing}")

            if routing == "VERIFIED":
                logger.info(f"Verification passed, terminating graph")
                break

            # Increment iteration counter
            state.iteration_count += 1

        state.execution_end_time = time.time()

        logger.info(
            f"Graph execution complete for tenant {tenant_id}: "
            f"{state.iteration_count} iterations, "
            f"{state.execution_time_ms:.1f}ms, "
            f"coverage={state.verification_coverage:.1%}"
        )

        return state

    async def _safe_node_exec(self, node_func, state: AgentState, node_name: str) -> AgentState:
        """Safely execute node with error handling.

        Args:
            node_func: Node function to execute
            state: Current state
            node_name: Node name for logging

        Returns:
            Updated state (or original if error)
        """
        try:
            logger.debug(f"Executing node: {node_name}")
            return await node_func(state)

        except Exception as e:
            logger.error(f"Error in {node_name} node: {e}")
            state.add_message(node_name, f"Error: {e}")
            return state

    async def _emit_event(self, event_type: str, state: AgentState) -> None:
        """Emit streaming event for long-running executions.

        Args:
            event_type: Event type (e.g., 'iteration_start')
            state: Current state
        """
        if not self.config.streaming_enabled:
            return

        event = {
            "type": event_type,
            "iteration": state.iteration_count,
            "coverage": state.verification_coverage,
            "timestamp": time.time(),
        }

        for callback in self.streaming_callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in streaming callback: {e}")

    def add_streaming_callback(self, callback) -> None:
        """Register callback for streaming events.

        Args:
            callback: Async callable(event: dict) -> None
        """
        self.streaming_callbacks.append(callback)

    def remove_streaming_callback(self, callback) -> None:
        """Unregister streaming callback."""
        if callback in self.streaming_callbacks:
            self.streaming_callbacks.remove(callback)


def get_graph() -> ContextVerificationGraph | NoOpAgent:
    """Get singleton graph instance (no-op if disabled)."""
    config = AgentConfig()
    if not config.enabled:
        return NoOpAgent()
    return ContextVerificationGraph()
