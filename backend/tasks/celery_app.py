"""Celery application initialization and broker setup."""

from __future__ import annotations

from celery import Celery

from backend.tasks.config import get_celery_config


def create_celery_app() -> Celery | None:
    """Create and configure Celery app.

    Returns None if Celery disabled or Redis unavailable.
    """
    config = get_celery_config()

    if not config.celery_enabled:
        return None

    try:
        app = Celery("casl_tasks")
        app.config_from_object(config.get_celery_config_dict())
        return app
    except Exception as e:
        print(f"Failed to initialize Celery: {e}")
        return None


# Singleton instance
_celery_app: Celery | None = None


def get_celery() -> Celery | None:
    """Get or create Celery app singleton."""
    global _celery_app
    if _celery_app is None:
        _celery_app = create_celery_app()
    return _celery_app


def is_celery_available() -> bool:
    """Check if Celery is available and enabled."""
    app = get_celery()
    return app is not None
