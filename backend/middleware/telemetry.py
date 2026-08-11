"""OpenTelemetry middleware for automatic HTTP request tracing.

Extracts W3C trace context from headers, creates root spans for each request,
and adds trace_id to response headers for client correlation.
"""

import time
import logging
from typing import Callable
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.observability.tracer import get_tracer, get_tracing_config

logger = logging.getLogger(__name__)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for distributed tracing of HTTP requests."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.config = get_tracing_config()
        self.tracer = get_tracer()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with tracing context."""

        # Extract trace context from W3C traceparent header or generate new trace ID
        trace_id = self._extract_or_generate_trace_id(request)
        tenant_id = request.headers.get("X-Tenant-ID", "default")

        # Create root span for HTTP request
        span_name = f"{request.method} {request.url.path}"
        span_attributes = {
            "http.method": request.method,
            "http.url": str(request.url),
            "http.target": request.url.path,
            "http.host": request.url.netloc,
            "http.scheme": request.url.scheme,
            "http.client_ip": self._get_client_ip(request),
            "tenant_id": tenant_id,
            "trace_id": trace_id,
        }

        with self.tracer.start_as_current_span(span_name) as span:
            for key, value in span_attributes.items():
                span.set_attribute(key, value)

            start_time = time.time()

            try:
                response = await call_next(request)
                elapsed_ms = (time.time() - start_time) * 1000

                # Record response attributes
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.response_time_ms", round(elapsed_ms, 2))

                # Add trace_id to response header for client correlation
                response.headers["X-Trace-ID"] = trace_id

                logger.debug(
                    f"Request traced: {request.method} {request.url.path} "
                    f"(status={response.status_code}, trace_id={trace_id}, "
                    f"elapsed={elapsed_ms:.1f}ms)"
                )

                return response

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                span.set_attribute("error", True)
                span.set_attribute("http.response_time_ms", round(elapsed_ms, 2))
                span.record_exception(e)

                logger.error(
                    f"Request error: {request.method} {request.url.path} "
                    f"(trace_id={trace_id}, error={type(e).__name__})"
                )

                raise

    def _extract_or_generate_trace_id(self, request: Request) -> str:
        """Extract trace ID from W3C traceparent header or generate new one."""

        # Parse W3C traceparent: version-traceID-parentID-traceFlags
        traceparent = request.headers.get("traceparent", "").split("-")

        if len(traceparent) >= 2:
            return traceparent[1]  # Extract trace ID

        # Fallback to X-Trace-ID header
        trace_id = request.headers.get("X-Trace-ID")
        if trace_id:
            return trace_id

        # Generate new trace ID
        return uuid.uuid4().hex

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers with X-Forwarded-For fallback."""

        if "X-Forwarded-For" in request.headers:
            return request.headers["X-Forwarded-For"].split(",")[0].strip()

        if request.client:
            return request.client.host

        return "unknown"
