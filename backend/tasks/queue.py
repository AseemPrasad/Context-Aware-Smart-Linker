"""Queue management and prioritization."""

from __future__ import annotations

from enum import Enum
from typing import Any

from backend.tasks.config import get_celery_config


class Priority(str, Enum):
    """Task priority levels."""

    HIGH = "high_priority"
    DEFAULT = "default"
    LOW = "batch_indexing"


class QueueManager:
    """Manages task queues and routing."""

    def __init__(self) -> None:
        """Initialize queue manager."""
        self.config = get_celery_config()

    def get_queue_name(self, priority: str | Priority = Priority.DEFAULT) -> str:
        """Get queue name for priority level."""
        if isinstance(priority, Priority):
            priority = priority.value

        queue_map = {
            Priority.HIGH.value: "high_priority",
            Priority.DEFAULT.value: "default",
            Priority.LOW.value: "batch_indexing",
        }

        return queue_map.get(priority, "default")

    def get_route_for_task(self, task_name: str, priority: str = Priority.DEFAULT) -> dict[str, Any]:
        """Get routing configuration for task."""
        queue_name = self.get_queue_name(priority)

        return {
            "queue": queue_name,
            "routing_key": queue_name,
            "exchange": queue_name,
        }

    def get_queue_stats(self, queue_name: str) -> dict[str, Any]:
        """Get stats for a queue."""
        # Placeholder: real implementation would query Celery
        return {
            "queue": queue_name,
            "length": 0,
            "processing": 0,
            "priority": self.config.queues[queue_name]["priority"] if self.config.queues else 0,
        }

    def get_all_queue_stats(self) -> dict[str, dict[str, Any]]:
        """Get stats for all queues."""
        stats = {}
        for queue_name in self.config.queues.keys() if self.config.queues else []:
            stats[queue_name] = self.get_queue_stats(queue_name)
        return stats

    def get_worker_config(self, priority: str = Priority.DEFAULT) -> dict[str, int]:
        """Get worker configuration for priority level."""
        if isinstance(priority, Priority):
            priority = priority.value

        if priority == Priority.HIGH.value:
            return {"concurrency": self.config.celery_high_priority_worker_concurrency}
        elif priority == Priority.LOW.value:
            return {"concurrency": self.config.celery_batch_worker_concurrency}
        else:
            return {"concurrency": self.config.celery_worker_concurrency}


def get_queue_manager() -> QueueManager:
    """Get queue manager singleton."""
    if not hasattr(get_queue_manager, "_instance"):
        get_queue_manager._instance = QueueManager()
    return get_queue_manager._instance
