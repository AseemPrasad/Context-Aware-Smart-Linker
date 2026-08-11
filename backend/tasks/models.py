"""Task state and result models for async processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    """Task execution state."""

    PENDING = "pending"
    STARTED = "started"
    RETRY = "retry"
    SUCCESS = "success"
    FAILURE = "failure"
    REVOKED = "revoked"


@dataclass
class TaskResult:
    """Complete task result with metadata."""

    task_id: str
    state: TaskState
    progress: int = 0  # 0-100
    result: Any = None
    error: str | None = None
    traceback: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status_message: str = ""

    def is_finished(self) -> bool:
        """Check if task is finished."""
        return self.state in (TaskState.SUCCESS, TaskState.FAILURE, TaskState.REVOKED)

    def is_failed(self) -> bool:
        """Check if task failed."""
        return self.state == TaskState.FAILURE

    def is_successful(self) -> bool:
        """Check if task succeeded."""
        return self.state == TaskState.SUCCESS

    def is_running(self) -> bool:
        """Check if task is running."""
        return self.state in (TaskState.STARTED, TaskState.RETRY)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "status_message": self.status_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class TaskMetadata:
    """Metadata for tracking long-running operations."""

    task_id: str
    task_name: str
    priority: str = "default"
    retry_count: int = 0
    queue_name: str = "default"
    started_at: datetime | None = None
    last_update_at: datetime = field(default_factory=datetime.utcnow)
    estimated_completion: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "priority": self.priority,
            "retry_count": self.retry_count,
            "queue_name": self.queue_name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_update_at": self.last_update_at.isoformat(),
        }
