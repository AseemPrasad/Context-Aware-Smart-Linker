"""CASL backend API gateway.

This module wires up the FastAPI application and exposes the ingestion and
search endpoints that route to the retrieval engine. It is intentionally kept
minimal and additive so the existing browser extension continues to work
independently.
"""

import os
from fastapi import FastAPI

from backend.api.routes import router
from backend.api.stream_endpoints import router as stream_router
from backend.cache.monitor import get_cache_monitor
from backend.gateway.endpoint import router as gateway_router
from backend.middleware.telemetry import TelemetryMiddleware
from backend.observability.tracer import setup_telemetry
from backend.security.middleware import AuthMiddleware, RateLimitMiddleware
from backend.security.monitor import get_security_monitor
from backend.tasks.endpoints import router as tasks_router
from backend.tasks.monitoring import router as monitoring_router

# Initialize OpenTelemetry tracing
setup_telemetry()

app = FastAPI(
    title="CASL Backend",
    description="Multi-tenant hybrid RAG retrieval engine.",
    version="0.1.0",
)

# Add authentication middleware (optional)
if os.getenv("AUTH_ENABLED", "false").lower() == "true":
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)

# Add telemetry middleware for HTTP request tracing
app.add_middleware(TelemetryMiddleware)

app.include_router(router)
app.include_router(gateway_router)
app.include_router(tasks_router)
app.include_router(monitoring_router)
app.include_router(stream_router)


@app.get("/health")
async def health() -> dict:
    """Simple health check for the API gateway."""
    return {"status": "ok"}


@app.get("/cache/stats")
async def cache_stats() -> dict:
    """Get cache performance statistics and health status."""
    monitor = get_cache_monitor()
    return monitor.get_stats().to_dict()


@app.get("/security/stats")
async def security_stats() -> dict:
    """Get security guardrails statistics and health status."""
    monitor = get_security_monitor()
    return monitor.get_stats().to_dict()


@app.get("/telemetry/metrics")
async def telemetry_metrics() -> dict:
    """Get OpenTelemetry metrics (Prometheus format exported as JSON)."""
    from backend.observability.metrics import get_token_budget_manager

    budget_manager = get_token_budget_manager()
    return budget_manager.get_metrics()


@app.get("/evals/metrics")
async def evals_metrics() -> dict:
    """Get latest evaluation metrics (if evaluation enabled)."""
    try:
        from evals.eval_harness import get_harness

        harness = get_harness()
        return harness.get_latest_metrics()
    except ImportError:
        return {"error": "Evaluation module not available", "enabled": False}


@app.get("/agents/metrics")
async def agents_metrics() -> dict:
    """Get agent execution metrics and health status."""
    try:
        from backend.agents.safety import get_monitor
        from backend.agents.config import get_config

        config = get_config()
        monitor = get_monitor()

        is_healthy, status_msg = monitor.check_health()

        return {
            "enabled": config.enabled,
            "healthy": is_healthy,
            "status": status_msg,
            "metrics": monitor.get_stats(),
        }
    except ImportError:
        return {"error": "Agent module not available", "enabled": False}


@app.post("/auth/token")
async def issue_token(tenant_id: str, user_id: str = None, user_role: str = "viewer") -> dict:
    """Issue JWT authentication token."""
    from backend.security.token_manager import get_token_manager

    manager = get_token_manager()
    token = manager.issue_token(tenant_id, user_id, user_role)

    return {"token": token, "type": "bearer"}


@app.post("/auth/token/refresh")
async def refresh_token(token: str) -> dict:
    """Refresh JWT token."""
    from backend.security.token_manager import get_token_manager

    manager = get_token_manager()
    new_token = manager.refresh_token(token)

    if not new_token:
        return {"error": "Invalid token"}, 401

    return {"token": new_token, "type": "bearer"}


@app.get("/security/status")
async def security_status() -> dict:
    """Get security system status."""
    from backend.security.auth import JWTConfig
    from backend.security.rate_limiter import RateLimitConfig
    from backend.security.rbac import RBACConfig

    return {
        "auth_enabled": JWTConfig().enabled,
        "rate_limit_enabled": RateLimitConfig().enabled,
        "rbac_enabled": RBACConfig().enabled,
    }
