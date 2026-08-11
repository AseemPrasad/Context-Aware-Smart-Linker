"""Authentication and rate limiting middleware."""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.security.auth import TokenValidator, TenantContext, JWTConfig
from backend.security.rate_limiter import RateLimiter, RateLimitConfig

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT authentication middleware."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.jwt_config = JWTConfig()
        self.validator = TokenValidator()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Extract and validate JWT token.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            Response from next handler
        """
        # Extract JWT from Authorization header
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header else None

        if token:
            # Validate token
            payload = self.validator.validate(token)

            if payload:
                # Set context
                TenantContext.set_context(payload)
                request.state.tenant_id = payload.tenant_id
                request.state.user_id = payload.user_id
                request.state.user_role = payload.user_role
                logger.debug(f"Auth success: tenant={payload.tenant_id}, role={payload.user_role}")
            else:
                if self.jwt_config.require_auth:
                    logger.warning("Invalid token and REQUIRE_AUTH=true")
                    return Response(status_code=401, content="Unauthorized")
                else:
                    logger.debug("Invalid token but REQUIRE_AUTH=false, allowing")
                    TenantContext.set_context(
                        __import__("backend.security.auth", fromlist=["JWTPayload"]).JWTPayload(
                            tenant_id="default", user_role="viewer"
                        )
                    )
        else:
            # No token provided
            if self.jwt_config.require_auth:
                logger.warning("Missing token and REQUIRE_AUTH=true")
                return Response(status_code=401, content="Unauthorized")
            else:
                logger.debug("Missing token but REQUIRE_AUTH=false, using default")
                TenantContext.set_context(
                    __import__("backend.security.auth", fromlist=["JWTPayload"]).JWTPayload(
                        tenant_id="default", user_role="viewer"
                    )
                )

        # Call next middleware
        response = await call_next(request)

        # Add headers
        if hasattr(request.state, "tenant_id"):
            response.headers["X-Tenant-ID"] = request.state.tenant_id
        if hasattr(request.state, "user_id"):
            response.headers["X-User-ID"] = request.state.user_id

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiting middleware."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.rate_limit_config = RateLimitConfig()
        self.limiter = RateLimiter()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit before executing request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            Response from next handler or 429 if rate limited
        """
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Get tenant
        tenant_id = TenantContext.get_current_tenant()
        endpoint = request.url.path

        # Check rate limit
        allowed, remaining, reset_seconds = await self.limiter.acquire(tenant_id, endpoint)

        if not allowed:
            logger.warning(
                f"Rate limit exceeded: tenant={tenant_id}, "
                f"endpoint={endpoint}, reset_in={reset_seconds}s"
            )
            return Response(
                status_code=429,
                content=f"Too many requests. Reset in {reset_seconds}s",
                headers={
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + reset_seconds),
                },
            )

        # Call next middleware
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

        return response
