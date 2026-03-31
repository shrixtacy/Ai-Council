"""OpenTelemetry tracing setup for AI Council."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
import os

_IS_SETUP = False

def setup_tracing(service_name: str = "ai_council_orchestrator"):
    """Initialize OpenTelemetry tracing."""
    global _IS_SETUP
    if _IS_SETUP:
        return trace.get_tracer(service_name)
    
    # We use a simple resource matching the service name
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    
    # Exporter points to Jaeger/OTLP collector (localhost:4318 by default)
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    
    # Set the global tracer provider
    trace.set_tracer_provider(provider)
    _IS_SETUP = True
    
    return trace.get_tracer(service_name)

def get_tracer(name: str):
    """Retrieve the initialized tracer."""
    return trace.get_tracer(name)
