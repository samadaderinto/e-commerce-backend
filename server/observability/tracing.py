import os
import threading

from django.conf import settings
from opentelemetry import trace

_provider = None
_pid = None
_lock = threading.Lock()


def tracer():
    global _provider, _pid
    if not settings.OTEL_TRACING_ENABLED:
        return trace.NoOpTracer()
    # Start export threads inside workers, never at module import before fork.
    with _lock:
        if _pid != os.getpid():
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

            ratio = float(os.environ.get('OTEL_TRACES_SAMPLER_ARG', '0.1'))
            _provider = TracerProvider(
                resource=Resource.create({'service.name': os.environ.get('OTEL_SERVICE_NAME', 'commerce-api')}),
                # Do not allow a public caller to force sampling with traceparent.
                sampler=TraceIdRatioBased(ratio),
            )
            _provider.add_span_processor(BatchSpanProcessor(
                OTLPSpanExporter(timeout=2), max_queue_size=512, max_export_batch_size=128,
            ))
            _pid = os.getpid()
    return _provider.get_tracer('commerce-api')
