"""OpenTelemetry distributed tracing infrastructure.

Provides singleton tracer initialization, span management, and context propagation.
Returns no-op tracer if telemetry is disabled (default).
"""

import os
import logging
from typing import Optional
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Tracer, Span

logger = logging.getLogger(__name__)


class TracingConfig:
    """Configuration for distributed tracing."""

    def __init__(self):
        self.enabled = os.getenv("TELEMETRY_ENABLED", "false").lower() == "true"
        self.otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        self.jaeger_enabled = os.getenv("JAEGER_ENABLED", "false").lower() == "true"
        self.jaeger_host = os.getenv("JAEGER_HOST", "localhost")
        self.jaeger_port = int(os.getenv("JAEGER_PORT", "6831"))
        self.sampler = os.getenv("OTEL_TRACES_SAMPLER", "parentbased_traceidratio")
        self.sampler_arg = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"))
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "casl-backend")


class NoOpTracer:
    """No-op tracer stub for when telemetry is disabled."""

    def start_as_current_span(self, name: str, **kwargs):
        return NoOpSpan()

    def start_span(self, name: str, **kwargs):
        return NoOpSpan()


class NoOpSpan:
    """No-op span stub."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def set_attribute(self, key: str, value):
        pass

    def add_event(self, name: str, attributes=None):
        pass

    def record_exception(self, exception: Exception):
        pass


_tracer: Optional[Tracer] = None
_tracer_config: Optional[TracingConfig] = None


def setup_telemetry() -> None:
    """Initialize OpenTelemetry SDK if enabled via TELEMETRY_ENABLED env var."""
    global _tracer, _tracer_config

    _tracer_config = TracingConfig()

    if not _tracer_config.enabled:
        logger.info("Telemetry disabled (set TELEMETRY_ENABLED=true to enable)")
        _tracer = NoOpTracer()
        return

    logger.info(f"Initializing OpenTelemetry with service={_tracer_config.service_name}")

    try:
        provider = TracerProvider()

        if _tracer_config.jaeger_enabled:
            jaeger_exporter = JaegerExporter(
                agent_host_name=_tracer_config.jaeger_host,
                agent_port=_tracer_config.jaeger_port,
            )
            provider.add_span_processor(SimpleSpanProcessor(jaeger_exporter))
            logger.info(f"Configured Jaeger exporter: {_tracer_config.jaeger_host}:{_tracer_config.jaeger_port}")
        else:
            otlp_exporter = OTLPSpanExporter(endpoint=_tracer_config.otel_endpoint)
            provider.add_span_processor(SimpleSpanProcessor(otlp_exporter))
            logger.info(f"Configured OTEL exporter: {_tracer_config.otel_endpoint}")

        trace.set_tracer_provider(provider)
        _tracer = provider.get_tracer(__name__)
        logger.info("OpenTelemetry initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}. Falling back to no-op tracer.")
        _tracer = NoOpTracer()


def get_tracer() -> Tracer:
    """Get the singleton tracer instance (no-op if disabled)."""
    global _tracer

    if _tracer is None:
        setup_telemetry()

    return _tracer


def get_tracing_config() -> TracingConfig:
    """Get the tracing configuration."""
    global _tracer_config

    if _tracer_config is None:
        _tracer_config = TracingConfig()

    return _tracer_config


@contextmanager
def with_trace_span(name: str, attributes: dict = None):
    """Context manager for manual span creation.

    Usage:
        with with_trace_span("my_operation", {"key": "value"}) as span:
            do_work()
            span.set_attribute("result", "success")
    """
    tracer = get_tracer()
    span = tracer.start_as_current_span(name)

    try:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span
    except Exception as e:
        span.record_exception(e)
        raise
    finally:
        span.end()
