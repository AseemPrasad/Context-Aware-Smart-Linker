"""Task monitoring and management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.tasks.backend import get_result_backend
from backend.tasks.celery_app import get_celery, is_celery_available
from backend.tasks.queue import get_queue_manager

router = APIRouter(prefix="/api/v1/tasks/admin", tags=["tasks-admin"])


@router.get("/queue/stats")
async def get_queue_stats() -> dict:
    """Get statistics for all queues."""
    if not is_celery_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing not available",
        )

    try:
        manager = get_queue_manager()
        return {"queues": manager.get_all_queue_stats()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/worker/stats")
async def get_worker_stats() -> dict:
    """Get worker pool statistics."""
    if not is_celery_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing not available",
        )

    try:
        app = get_celery()
        stats = app.control.inspect().stats()

        return {
            "workers": stats or {},
            "total_workers": len(stats) if stats else 0,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/tasks/active")
async def get_active_tasks() -> dict:
    """Get list of actively running tasks."""
    if not is_celery_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing not available",
        )

    try:
        app = get_celery()
        active = app.control.inspect().active()

        task_list = []
        if active:
            for worker_tasks in active.values():
                task_list.extend(worker_tasks)

        return {
            "active_tasks": task_list,
            "count": len(task_list),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/tasks/pending")
async def get_pending_tasks() -> dict:
    """Get list of pending/queued tasks."""
    if not is_celery_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing not available",
        )

    try:
        backend = get_result_backend()
        if not backend:
            return {"pending_tasks": [], "count": 0}

        pending = backend.get_all_pending_tasks()
        return {
            "pending_tasks": [t.to_dict() for t in pending],
            "count": len(pending),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/queue/{queue_name}/clear")
async def clear_queue(queue_name: str) -> dict:
    """Clear a queue (admin only)."""
    if not is_celery_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing not available",
        )

    if queue_name not in ["high_priority", "default", "batch_indexing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid queue: {queue_name}",
        )

    try:
        app = get_celery()
        app.control.discard_all()  # Discard all tasks

        return {
            "queue": queue_name,
            "status": "cleared",
            "message": f"Queue {queue_name} has been cleared",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
