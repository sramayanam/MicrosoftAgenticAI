"""
Shared observability configuration for distributed tracing across all components.

This module provides a unified approach to configure Azure Application Insights
telemetry for the entire multi-agent system including:
- Frontend (Streamlit)
- Orchestrator
- SQL Foundry Agent
- Python Tool Agent

All traces will be correlated in Azure Application Insights for end-to-end visibility.
"""

import atexit
import logging
import os
import signal
import sys
from typing import Optional

from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import set_tracer_provider
from opentelemetry.trace.span import format_trace_id

load_dotenv()

# Global configuration
APPINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
_is_configured = False
_tracer_provider = None
_original_sigint_handler = None




def _handle_sigint(signum, frame):
    """Handle Ctrl+C - force immediate shutdown"""
    global _tracer_provider, _original_sigint_handler

    if _tracer_provider:
        try:
            # Try quick flush (500ms max)
            _tracer_provider.force_flush(timeout_millis=500)
        except Exception:
            pass

        try:
            _tracer_provider.shutdown()
        except Exception:
            pass

    # Call original handler or exit
    if _original_sigint_handler:
        _original_sigint_handler(signum, frame)
    else:
        sys.exit(0)


def _shutdown_telemetry():
    """Gracefully shutdown telemetry with timeout"""
    global _tracer_provider
    if _tracer_provider:
        try:
            # Force flush with very short timeout
            _tracer_provider.force_flush(timeout_millis=1000)  # 1 second max
        except Exception:
            pass  # Ignore flush errors

        try:
            # Shutdown with timeout
            _tracer_provider.shutdown()
        except Exception:
            pass  # Ignore shutdown errors


def configure_observability(
    service_name: str,
    connection_string: Optional[str] = None,
    enable_logging: bool = True,
    enable_tracing: bool = True,
    enable_httpx_instrumentation: bool = True,
    log_namespaces_to_exclude: Optional[list[str]] = None,
) -> bool:
    """
    Configure observability for the service with Azure Application Insights.

    Args:
        service_name: Name of the service (e.g., "streamlit-frontend", "sql-foundry-agent")
        connection_string: Azure Application Insights connection string (defaults to env var)
        enable_logging: Enable logging telemetry
        enable_tracing: Enable distributed tracing
        enable_httpx_instrumentation: Enable automatic HTTPX request tracing
        log_namespaces_to_exclude: List of namespaces to exclude from logging (e.g., ["semantic_kernel.functions"])

    Returns:
        bool: True if observability was configured, False if connection string is not available
    """
    global _is_configured, _tracer_provider, _original_sigint_handler

    conn_str = connection_string or APPINSIGHTS_CONNECTION_STRING

    if not conn_str:
        print(
            f"⚠️  [{service_name}] APPLICATIONINSIGHTS_CONNECTION_STRING not set - observability disabled"
        )
        return False

    if _is_configured:
        print(
            f"ℹ️  [{service_name}] Observability already configured, skipping re-configuration"
        )
        return True

    print(
        f"✅ [{service_name}] Configuring observability - sending telemetry to Azure Application Insights"
    )

    try:
        # Create resource
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: service_name,
        })

        # Create Azure Monitor exporter with shorter timeout
        exporter = AzureMonitorTraceExporter(
            connection_string=conn_str,
        )

        # Create tracer provider with batch processor (shorter intervals)
        _tracer_provider = TracerProvider(resource=resource)

        # Use BatchSpanProcessor with very aggressive timeouts to prevent hanging
        span_processor = BatchSpanProcessor(
            exporter,
            max_queue_size=512,  # Smaller queue
            schedule_delay_millis=2000,  # Export every 2 seconds
            export_timeout_millis=5000,  # 5 second export timeout (was 10)
            max_export_batch_size=128,  # Smaller batches
        )
        _tracer_provider.add_span_processor(span_processor)

        # Set as global tracer provider
        set_tracer_provider(_tracer_provider)

        # Register shutdown handlers
        atexit.register(_shutdown_telemetry)

        # Try to override SIGINT (Ctrl+C) to handle shutdown quickly
        # This only works in main thread, so we catch the exception
        try:
            _original_sigint_handler = signal.signal(signal.SIGINT, _handle_sigint)
            print(f"   ✓ Signal handler registered")
        except ValueError:
            # Not in main thread (e.g., Streamlit), skip signal handler
            pass

        print(f"   ✓ Distributed tracing configured")
    except Exception as e:
        print(f"   ⚠️  Failed to configure Azure Monitor: {e}")
        return False

    # Setup automatic instrumentation for HTTPX (used by A2A SDK)
    if enable_httpx_instrumentation:
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
            print(f"   ✓ HTTPX instrumentation enabled (A2A calls will be traced)")
        except Exception as e:
            print(f"   ⚠ HTTPX instrumentation failed: {e}")

    # Mark as configured
    _is_configured = True
    return True


def get_tracer(name: str) -> trace.Tracer:
    """
    Get a tracer for the specified module.

    Args:
        name: Name of the module (typically __name__)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID if available.

    Returns:
        Formatted trace ID string or None if no active span
    """
    current_span = trace.get_current_span()
    if current_span and current_span.get_span_context().trace_id:
        return format_trace_id(current_span.get_span_context().trace_id)
    return None


def get_trace_context_headers() -> dict[str, str]:
    """
    Get W3C trace context headers for distributed tracing propagation.

    Returns:
        Dictionary with traceparent and tracestate headers if available
    """
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    headers = {}
    propagator = TraceContextTextMapPropagator()
    propagator.inject(headers)
    return headers


def inject_trace_context(headers: dict[str, str]) -> dict[str, str]:
    """
    Inject current trace context into HTTP headers for distributed tracing.

    Args:
        headers: Existing headers dictionary to inject trace context into

    Returns:
        Updated headers dictionary with trace context
    """
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    propagator = TraceContextTextMapPropagator()
    propagator.inject(headers)
    return headers


def extract_trace_context(headers: dict[str, str]) -> trace.SpanContext:
    """
    Extract trace context from HTTP headers for distributed tracing.

    Args:
        headers: HTTP headers containing trace context

    Returns:
        SpanContext extracted from headers
    """
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry import context as otel_context

    propagator = TraceContextTextMapPropagator()
    ctx = propagator.extract(headers)
    return trace.get_current_span(ctx).get_span_context()


def print_trace_info():
    """Print current trace information with Azure Portal link"""
    trace_id = get_current_trace_id()
    if trace_id:
        print(f"🔍 Trace ID: {trace_id}")
        print(f"   View in Application Insights: https://portal.azure.com")
    else:
        print("ℹ️  No active trace")


def enable_observability_decorator(service_name: str):
    """
    A decorator to enable observability for async functions.

    Usage:
        @enable_observability_decorator("my-service")
        async def main():
            # Your code here
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Configure observability
            is_configured = configure_observability(service_name)

            if not is_configured:
                # Run without observability
                return await func(*args, **kwargs)

            # Create a root span for the main function
            tracer = get_tracer(__name__)
            with tracer.start_as_current_span(f"{service_name}.main") as span:
                span.set_attribute("service.name", service_name)
                print_trace_info()
                return await func(*args, **kwargs)

        return wrapper

    return decorator
