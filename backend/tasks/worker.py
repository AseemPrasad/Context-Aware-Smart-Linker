"""Celery worker process entry point.

Run with: python -m backend.tasks.worker
"""

from __future__ import annotations

import logging
import signal
import sys

from backend.tasks.celery_app import get_celery
from backend.tasks.config import get_celery_config
from backend.tasks.jobs import register_tasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Start Celery worker."""
    config = get_celery_config()

    if not config.celery_enabled:
        logger.error("Celery is not enabled. Set CELERY_ENABLED=true to start worker.")
        sys.exit(1)

    app = get_celery()
    if not app:
        logger.error("Failed to initialize Celery. Check Redis connection.")
        sys.exit(1)

    # Register all tasks
    register_tasks()

    logger.info("Starting Celery worker...")
    logger.info(f"Broker: {config.redis_broker_url}")
    logger.info(f"Result backend: {config.celery_result_backend}")
    logger.info(f"Concurrency: {config.celery_worker_concurrency}")

    # Setup signal handlers for graceful shutdown
    def handle_sigterm(sig: int, frame: object) -> None:
        logger.info("SIGTERM received, shutting down gracefully...")
        sys.exit(0)

    def handle_sigint(sig: int, frame: object) -> None:
        logger.info("SIGINT received, shutting down gracefully...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigint)

    # Start worker
    try:
        worker = app.Worker(
            queues=["high_priority", "default", "batch_indexing"],
            loglevel="info",
            concurrency=config.celery_worker_concurrency,
            prefetch_multiplier=config.celery_worker_prefetch_multiplier,
            max_tasks_per_child=config.celery_max_tasks_per_child,
        )
        worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
