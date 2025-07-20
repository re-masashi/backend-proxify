# app/telemetry.py
import os

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_telemetry(app):
    """Configure OpenTelemetry for the FastAPI application."""

    # Configure tracing
    resource = Resource(
        attributes={
            SERVICE_NAME: "proxify-api",
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    # Set up tracer provider
    trace.set_tracer_provider(TracerProvider(resource=resource))

    # Configure Jaeger exporter (optional - for trace visualization)
    jaeger_exporter = JaegerExporter(
        agent_host_name=os.getenv("JAEGER_HOST", "localhost"),
        agent_port=int(os.getenv("JAEGER_PORT", "6831")),
    )

    # Add span processor
    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

    # Configure metrics (optional)
    prometheus_reader = PrometheusMetricReader()
    MeterProvider(
        resource=resource, metric_readers=[prometheus_reader]
    )

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Instrument requests (for outbound HTTP calls)
    RequestsInstrumentor().instrument()

    print("✅ OpenTelemetry configured successfully")
