"""Celery task definitions for async processing."""

from __future__ import annotations

import time
from typing import Any

from backend.tasks.celery_app import get_celery
from backend.tasks.models import TaskResult, TaskState
from backend.observability.tracer import get_tracer


def register_tasks() -> None:
    """Register all Celery tasks. Call once at startup."""
    app = get_celery()
    if not app:
        return

    @app.task(bind=True, name="backend.tasks.jobs.extract_webpage_task", queue="default")
    def extract_webpage_task(
        self: Any,
        url: str,
        context: str | None = None,
        x_trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Extract content from a webpage asynchronously.

        Args:
            url: URL to extract from
            context: Optional context to include
            x_trace_id: Trace ID from parent request for correlation

        Returns:
            Extracted content and metadata
        """
        tracer = get_tracer()
        task_start = time.time()

        with tracer.start_as_current_span("task.extraction") as span:
            span.set_attribute("task_id", self.request.id)
            span.set_attribute("task_name", self.name)
            span.set_attribute("url", url)
            if x_trace_id:
                span.set_attribute("parent_trace_id", x_trace_id)

            try:
                # Update progress
                self.update_state(state="PROGRESS", meta={"progress": 10, "status": "Fetching webpage"})

                # Simulate extraction (in real scenario, would use requests + BeautifulSoup)
                time.sleep(1)  # Placeholder for actual extraction

                self.update_state(state="PROGRESS", meta={"progress": 50, "status": "Processing content"})

                extracted_content = {
                    "url": url,
                    "title": "Extracted Page Title",
                    "text": "Extracted content from page",
                    "chunks": 5,
                    "tokens_estimated": 500,
                }

                self.update_state(state="PROGRESS", meta={"progress": 100, "status": "Complete"})

                task_duration_ms = (time.time() - task_start) * 1000
                span.set_attribute("duration_ms", round(task_duration_ms, 2))
                span.set_attribute("status", "success")

                return extracted_content

            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("status", "error")
                raise self.retry(exc=exc, countdown=60, max_retries=3)

    @app.task(bind=True, name="backend.tasks.jobs.process_and_embed_task", queue="default")
    def process_and_embed_task(
        self: Any,
        content: str,
        document_id: str,
        x_trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Process content and generate embeddings.

        Args:
            content: Text content to process
            document_id: ID of document
            x_trace_id: Trace ID from parent request for correlation

        Returns:
            Processing results and metadata
        """
        tracer = get_tracer()
        task_start = time.time()

        with tracer.start_as_current_span("task.embedding") as span:
            span.set_attribute("task_id", self.request.id)
            span.set_attribute("task_name", self.name)
            span.set_attribute("document_id", document_id)
            if x_trace_id:
                span.set_attribute("parent_trace_id", x_trace_id)

            try:
                self.update_state(state="PROGRESS", meta={"progress": 20, "status": "Chunking content"})

                # Simulate chunking
                time.sleep(0.5)

                self.update_state(state="PROGRESS", meta={"progress": 50, "status": "Generating embeddings"})

                # Simulate embedding
                time.sleep(1)

                self.update_state(state="PROGRESS", meta={"progress": 80, "status": "Indexing"})

                result = {
                    "document_id": document_id,
                    "chunks_created": 5,
                    "tokens_used": 500,
                    "embeddings_generated": 5,
                }

                task_duration_ms = (time.time() - task_start) * 1000
                span.set_attribute("duration_ms", round(task_duration_ms, 2))
                span.set_attribute("status", "success")

                return result

            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("status", "error")
                raise self.retry(exc=exc, countdown=60, max_retries=3)

    @app.task(bind=True, name="backend.tasks.jobs.batch_extract_task", queue="batch_indexing")
    def batch_extract_task(
        self: Any,
        urls: list[str],
        priority: str = "default",
        x_trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Extract from multiple URLs in batch.

        Args:
            urls: List of URLs to extract from
            priority: Priority level for processing
            x_trace_id: Trace ID from parent request for correlation

        Returns:
            Aggregated results
        """
        tracer = get_tracer()
        task_start = time.time()

        with tracer.start_as_current_span("task.batch_extraction") as span:
            span.set_attribute("task_id", self.request.id)
            span.set_attribute("task_name", self.name)
            span.set_attribute("batch_size", len(urls))
            span.set_attribute("priority", priority)
            if x_trace_id:
                span.set_attribute("parent_trace_id", x_trace_id)

            try:
                results = {}
                total = len(urls)

                for i, url in enumerate(urls):
                    progress = int((i / total) * 100)
                    self.update_state(
                        state="PROGRESS",
                        meta={"progress": progress, "status": f"Processing {i + 1}/{total}"},
                    )

                    # Simulate extraction
                    time.sleep(0.5)

                    results[url] = {"success": True, "chunks": 3}

                task_duration_ms = (time.time() - task_start) * 1000
                span.set_attribute("duration_ms", round(task_duration_ms, 2))
                span.set_attribute("status", "success")
                span.set_attribute("successful", total)
                span.set_attribute("failed", 0)

                return {
                    "total_urls": total,
                    "successful": total,
                    "failed": 0,
                    "results": results,
                }

            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("status", "error")
                raise self.retry(exc=exc, countdown=60, max_retries=3)

    @app.task(bind=True, name="backend.tasks.jobs.update_task_progress", queue="high_priority")
    def update_task_progress(
        self: Any,
        task_id: str,
        progress: int,
        status_message: str,
    ) -> None:
        """Update task progress in result backend.

        Args:
            task_id: Task ID to update
            progress: Progress percentage (0-100)
            status_message: Status message
        """
        # This task is internal, just returns
        return None


def get_task_by_name(task_name: str) -> Any:
    """Get Celery task by name."""
    app = get_celery()
    if not app:
        return None
    return app.tasks.get(task_name)
