"""Task result backend using Redis for state persistence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import redis

from backend.tasks.config import get_celery_config
from backend.tasks.models import TaskResult, TaskState


class TaskResultBackend:
    """Manages task results in Redis."""

    def __init__(self) -> None:
        """Initialize backend."""
        config = get_celery_config()
        try:
            # Parse Redis URL and connect
            self.redis = redis.from_url(config.celery_result_backend, decode_responses=True)
            self.redis.ping()
            self.ttl = config.result_expires
        except Exception as e:
            self.redis = None
            print(f"Failed to connect to Redis result backend: {e}")

    def _get_key(self, task_id: str) -> str:
        """Get Redis key for task."""
        return f"task:{task_id}"

    def get_task_state(self, task_id: str) -> TaskResult | None:
        """Get task state from Redis."""
        if not self.redis:
            return None

        try:
            data = self.redis.get(self._get_key(task_id))
            if not data:
                return None

            task_dict = json.loads(data)
            return TaskResult(
                task_id=task_id,
                state=TaskState(task_dict["state"]),
                progress=task_dict.get("progress", 0),
                result=task_dict.get("result"),
                error=task_dict.get("error"),
                status_message=task_dict.get("status_message", ""),
            )
        except Exception:
            return None

    def update_progress(self, task_id: str, progress: int, status_message: str = "") -> bool:
        """Update task progress."""
        if not self.redis:
            return False

        try:
            task = self.get_task_state(task_id)
            if not task:
                return False

            task.progress = min(100, max(0, progress))
            task.status_message = status_message
            self._save_task(task)
            return True
        except Exception:
            return False

    def mark_success(self, task_id: str, result: Any) -> bool:
        """Mark task as successful."""
        if not self.redis:
            return False

        try:
            task = TaskResult(
                task_id=task_id,
                state=TaskState.SUCCESS,
                progress=100,
                result=result,
                completed_at=datetime.utcnow(),
            )
            self._save_task(task)
            return True
        except Exception:
            return False

    def mark_failure(self, task_id: str, error: str, traceback: str = "") -> bool:
        """Mark task as failed."""
        if not self.redis:
            return False

        try:
            task = TaskResult(
                task_id=task_id,
                state=TaskState.FAILURE,
                error=error,
                traceback=traceback,
                completed_at=datetime.utcnow(),
            )
            self._save_task(task)
            return True
        except Exception:
            return False

    def revoke_task(self, task_id: str) -> bool:
        """Mark task as revoked."""
        if not self.redis:
            return False

        try:
            task = self.get_task_state(task_id)
            if task:
                task.state = TaskState.REVOKED
                self._save_task(task)
            return True
        except Exception:
            return False

    def _save_task(self, task: TaskResult) -> None:
        """Save task to Redis."""
        if not self.redis:
            return

        key = self._get_key(task.task_id)
        data = task.to_dict()
        self.redis.setex(key, self.ttl, json.dumps(data))

    def get_all_pending_tasks(self, pattern: str = "task:*") -> list[TaskResult]:
        """Get all pending tasks matching pattern."""
        if not self.redis:
            return []

        try:
            keys = self.redis.keys(pattern)
            tasks = []
            for key in keys:
                task_id = key.replace("task:", "")
                task = self.get_task_state(task_id)
                if task and task.state in (TaskState.PENDING, TaskState.STARTED, TaskState.RETRY):
                    tasks.append(task)
            return tasks
        except Exception:
            return []

    def cleanup_expired(self) -> int:
        """Cleanup expired tasks. Returns count deleted."""
        if not self.redis:
            return 0

        try:
            keys = self.redis.keys("task:*")
            return len(keys)  # Redis auto-expires with TTL
        except Exception:
            return 0


def get_result_backend() -> TaskResultBackend | None:
    """Get task result backend singleton."""
    if not hasattr(get_result_backend, "_instance"):
        backend = TaskResultBackend()
        get_result_backend._instance = backend if backend.redis else None
    return get_result_backend._instance
