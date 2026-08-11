"""CASL backend API gateway.

This module wires up the FastAPI application and exposes the ingestion and
search endpoints that route to the retrieval engine. It is intentionally kept
minimal and additive so the existing browser extension continues to work
independently.
"""

from fastapi import FastAPI

from backend.api.routes import router
from backend.cache.monitor import get_cache_monitor
from backend.gateway.endpoint import router as gateway_router
from backend.security.monitor import get_security_monitor
from backend.tasks.endpoints import router as tasks_router
from backend.tasks.monitoring import router as monitoring_router

app = FastAPI(
    title="CASL Backend",
    description="Multi-tenant hybrid RAG retrieval engine.",
    version="0.1.0",
)

app.include_router(router)
app.include_router(gateway_router)
app.include_router(tasks_router)
app.include_router(monitoring_router)


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
