"""Middleware integration for multi-agent context verification."""

import logging
import os
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.agents.state import AgentConfig
from backend.agents.graph import get_graph
from backend.agents.output import ContextAnchorGenerator, ContextAnchorValidator

logger = logging.getLogger(__name__)


class AgentMiddleware(BaseHTTPMiddleware):
    """Optional middleware for transparent agent context verification.

    Can be configured to verify context based on query parameters or headers.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.config = AgentConfig()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with optional agent verification.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            Response from next handler
        """
        # Check if agent verification is requested
        use_agents = request.query_params.get("use_agents", "").lower() == "true"

        if not use_agents or not self.config.enabled:
            # No agent verification requested, pass through
            return await call_next(request)

        # TODO: Extract context from request and run graph
        # For now, just pass through (agents would be called in specific endpoints)
        return await call_next(request)


class AgentSearchEndpoint:
    """Handler for `/search/verified` endpoint with agent verification."""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.graph = get_graph()

    async def handle_verified_search(self, query: str, tenant_id: str = "default") -> dict:
        """Execute search with agent verification.

        Args:
            query: Search query
            tenant_id: Tenant identifier

        Returns:
            Dict with verification results
        """
        if not self.config.enabled:
            logger.warning("Agents disabled, returning standard search")
            return {"error": "Agents not enabled"}

        # Execute agent graph
        state = await self.graph.execute(query, tenant_id=tenant_id)

        # Generate anchored output
        output = ContextAnchorGenerator.generate(state)

        # Validate output
        is_valid, errors = ContextAnchorValidator.validate(output)

        if not is_valid:
            logger.warning(f"Validation errors: {errors}")

        return output.to_dict()


class AgentOptimizationWrapper:
    """Wrapper for transparent agent integration with existing `/search` endpoint.

    Can be attached as a dependency to conditionally verify context.
    """

    def __init__(self):
        self.config = AgentConfig()
        self.graph = get_graph()

    async def maybe_verify(
        self, query: str, context: Optional[str] = None, tenant_id: str = "default"
    ) -> Optional[dict]:
        """Optionally verify context if available and agents enabled.

        Args:
            query: Search query
            context: Optional context to verify
            tenant_id: Tenant ID

        Returns:
            Verified anchored context or None if not applicable
        """
        if not self.config.enabled or not context:
            return None

        # Execute agent graph on context
        state = await self.graph.execute(context, tenant_id=tenant_id)

        # Check if verification passed
        if state.last_routing_key != "VERIFIED":
            logger.info(f"Agent verification did not pass: {state.last_routing_key}")
            return None

        # Generate and validate output
        output = ContextAnchorGenerator.generate(state)
        is_valid, errors = ContextAnchorValidator.validate(output)

        if not is_valid:
            logger.warning(f"Agent output validation failed: {errors}")
            return None

        return output.to_dict()


def get_agent_endpoint() -> AgentSearchEndpoint:
    """Get singleton agent search endpoint handler."""
    return AgentSearchEndpoint()


def get_agent_wrapper() -> AgentOptimizationWrapper:
    """Get singleton agent optimization wrapper."""
    return AgentOptimizationWrapper()
