"""Celery and task processing configuration.

Centralizes all async task settings with env var support.
All features disabled by default for backward compatibility.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class CeleryConfig:
    """Configuration for Celery task queue."""

    # Master feature flag
    celery_enabled: bool = os.getenv("CELERY_ENABLED", "false").lower() == "true"

    # Redis broker settings
    redis_broker_url: str = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    # Task execution settings
    celery_task_time_limit: int = int(os.getenv("CELERY_TASK_TIME_LIMIT", "600"))  # 10 minutes
    celery_task_soft_time_limit: int = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "540"))  # 9 minutes
    celery_task_acks_late: bool = os.getenv("CELERY_TASK_ACKS_LATE", "true").lower() == "true"
    celery_worker_prefetch_multiplier: int = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))

    # Worker settings
    celery_worker_concurrency: int = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))
    celery_high_priority_worker_concurrency: int = int(os.getenv("CELERY_HIGH_PRIORITY_WORKER_CONCURRENCY", "2"))
    celery_batch_worker_concurrency: int = int(os.getenv("CELERY_BATCH_WORKER_CONCURRENCY", "1"))
    celery_max_tasks_per_child: int = int(os.getenv("CELERY_MAX_TASKS_PER_CHILD", "1000"))

    # Result backend settings
    result_expires: int = int(os.getenv("CELERY_RESULT_EXPIRES", "86400"))  # 24 hours
    result_compression: str = os.getenv("CELERY_RESULT_COMPRESSION", "gzip")

    # Retry settings
    task_autoretry_for: tuple = (Exception,)
    task_max_retries: int = int(os.getenv("CELERY_MAX_RETRIES", "3"))
    task_default_retry_delay: int = int(os.getenv("CELERY_DEFAULT_RETRY_DELAY", "60"))  # 1 minute

    # Queue definitions with routing
    queues: dict = None

    def __post_init__(self) -> None:
        """Initialize queue definitions."""
        self.queues = {
            "high_priority": {
                "exchange": "high_priority",
                "routing_key": "high_priority",
                "priority": 10,
            },
            "default": {
                "exchange": "default",
                "routing_key": "default",
                "priority": 5,
            },
            "batch_indexing": {
                "exchange": "batch_indexing",
                "routing_key": "batch_indexing",
                "priority": 1,
            },
        }

    def get_celery_config_dict(self) -> dict:
        """Get Celery configuration as dictionary."""
        return {
            "broker_url": self.redis_broker_url,
            "result_backend": self.celery_result_backend,
            "task_serializer": "json",
            "accept_content": ["json"],
            "result_serializer": "json",
            "timezone": "UTC",
            "enable_utc": True,
            "task_track_started": True,
            "task_time_limit": self.celery_task_time_limit,
            "task_soft_time_limit": self.celery_task_soft_time_limit,
            "task_acks_late": self.celery_task_acks_late,
            "worker_prefetch_multiplier": self.celery_worker_prefetch_multiplier,
            "result_expires": self.result_expires,
            "task_compression": self.result_compression,
            "task_auto_retry_for": self.task_autoretry_for,
            "task_max_retries": self.task_max_retries,
            "task_default_retry_delay": self.task_default_retry_delay,
            "task_routes": self._get_task_routes(),
            "task_default_queue": "default",
            "task_default_exchange": "default",
            "task_default_routing_key": "default",
            "worker_max_tasks_per_child": self.celery_max_tasks_per_child,
            "queues": self._get_queues_config(),
        }

    def _get_task_routes(self) -> dict:
        """Get task routing configuration."""
        return {
            "backend.tasks.jobs.extract_webpage_task": {"queue": "default"},
            "backend.tasks.jobs.process_and_embed_task": {"queue": "default"},
            "backend.tasks.jobs.batch_extract_task": {"queue": "batch_indexing"},
            "backend.tasks.jobs.update_task_progress": {"queue": "high_priority"},
        }

    def _get_queues_config(self) -> dict:
        """Get queue configuration."""
        from kombu import Queue

        return {
            "high_priority": Queue("high_priority", priority=10),
            "default": Queue("default", priority=5),
            "batch_indexing": Queue("batch_indexing", priority=1),
        }


def get_celery_config() -> CeleryConfig:
    """Get Celery configuration singleton."""
    if not hasattr(get_celery_config, "_instance"):
        get_celery_config._instance = CeleryConfig()
    return get_celery_config._instance
