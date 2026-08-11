"""Streaming endpoints for metrics and monitoring."""
from fastapi import APIRouter
from backend.api.stream_metrics import get_metrics_collector

router = APIRouter(prefix="/api/v1/stream")

@router.get("/metrics")
async def get_stream_metrics() -> dict:
    """Get streaming metrics."""
    collector = get_metrics_collector()
    return {"metrics": collector.get_metrics()}
