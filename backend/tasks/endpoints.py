"""FastAPI endpoints for async task processing."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.tasks.backend import get_result_backend
from backend.tasks.celery_app import get_celery, is_celery_available
from backend.tasks.config import get_celery_config
from backend.tasks.jobs import register_tasks
from backend.tasks.models import TaskResult

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.on_event("startup")
async def startup_tasks() -> None:
    """Initialize tasks on startup."""
    if is_celery_available():
        register_tasks()


@router.post("/extract", status_code=status.HTTP_202_ACCEPTED)
async def extract_webpage(url: str, context: str | None = None) -> dict:
    """Submit webpage extraction task.

    Returns 202 Accepted with task_id for polling.
    """
    if not is_celery_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing not available",
        )

    try:
        app = get_celery()
        task = app.send_task("backend.tasks.jobs.extract_webpage_task", args=(url, context), queue="default")

        return {
            "task_id": task.id,
            "status": "accepted",
            "message": f"Extraction task {task.id} queued",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue task: {str(e)}",
        )


@router.post("/batch_extract", status_code=status.HTTP_202_ACCEPTED)
async def batch_extract(urls: list[str], priority: str = "default") -> dict:
    """Submit batch extraction task.

    Returns 202 Accepted with task_id for polling.
    """
    if not is_celery_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing not available",
        )

    if not urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URLs list cannot be empty",
        )

    try:
        app = get_celery()
        task = app.send_task(
            "backend.tasks.jobs.batch_extract_task",
            args=(urls, priority),
            queue="batch_indexing",
        )

        return {
            "task_id": task.id,
            "status": "accepted",
            "message": f"Batch extraction task {task.id} queued for {len(urls)} URLs",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue task: {str(e)}",
        )


@router.get("/task/{task_id}/status")
async def get_task_status(task_id: str) -> dict:
    """Poll task status.

    Returns current state, progress, result (if complete), or error.
    """
    if not is_celery_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing not available",
        )

    try:
        backend = get_result_backend()
        if not backend:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Result backend unavailable",
            )

        task_result = backend.get_task_state(task_id)
        if not task_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found",
            )

        return task_result.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}",
        )


@router.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict:
    """Cancel a running task."""
    if not is_celery_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing not available",
        )

    try:
        app = get_celery()
        app.control.revoke(task_id, terminate=True)

        backend = get_result_backend()
        if backend:
            backend.revoke_task(task_id)

        return {
            "task_id": task_id,
            "status": "revoked",
            "message": f"Task {task_id} cancelled",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}",
        )


@router.get("/config")
async def get_config() -> dict:
    """Get async processing configuration."""
    config = get_celery_config()

    return {
        "celery_enabled": config.celery_enabled,
        "broker_url": config.redis_broker_url.split("://")[0] if config.redis_broker_url else None,
        "worker_concurrency": config.celery_worker_concurrency,
        "task_time_limit": config.celery_task_time_limit,
        "queues": list(config.queues.keys()) if config.queues else [],
    }
