import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import get_settings
from app.database import engine

logger = logging.getLogger(__name__)

EXCLUDED_URLS = "/health$,/ready$,/metrics$"


def traces_url(endpoint: str) -> str:
    return f"{endpoint.rstrip('/')}/v1/traces"


def build_tracer_provider(service_name: str, endpoint: str) -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_url(endpoint))))
    return provider


def configure_tracing(service_name: str, app: FastAPI | None = None) -> bool:
    endpoint = get_settings().otel_exporter_otlp_endpoint
    if not endpoint:
        return False

    trace.set_tracer_provider(build_tracer_provider(service_name, endpoint))

    CeleryInstrumentor().instrument()

    SQLAlchemyInstrumentor().instrument(engine=engine, skip_dep_check=True)
    HTTPXClientInstrumentor().instrument()
    if app is not None:
        FastAPIInstrumentor.instrument_app(
            app, excluded_urls=EXCLUDED_URLS, exclude_spans=["receive", "send"]
        )

    logger.info("Tracing ativo", extra={"service_name": service_name, "otlp_endpoint": endpoint})
    return True
