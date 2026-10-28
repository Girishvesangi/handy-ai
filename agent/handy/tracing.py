"""Optional tracing to Langfuse through OpenTelemetry.

LiveKit Agents already emits OpenTelemetry spans for each turn, model call,
and tool call. If LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set, this
sends those spans to Langfuse, so you get a timeline of every session with
latency per step. Without the keys it does nothing.
"""

from __future__ import annotations

import base64
import logging
import os

logger = logging.getLogger("handy.tracing")


def setup_langfuse(session_id: str) -> bool:
    public, secret = os.getenv("LANGFUSE_PUBLIC_KEY"), os.getenv("LANGFUSE_SECRET_KEY")
    if not (public and secret):
        return False

    from livekit.agents.telemetry import set_tracer_provider
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    host = (os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com").rstrip("/")
    auth = base64.b64encode(f"{public}:{secret}".encode()).decode()
    exporter = OTLPSpanExporter(
        endpoint=f"{host}/api/public/otel/v1/traces",
        headers={"Authorization": f"Basic {auth}"},
    )
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    set_tracer_provider(provider, metadata={"langfuse.session.id": session_id})
    logger.info("sending traces to Langfuse at %s", host)
    return True
