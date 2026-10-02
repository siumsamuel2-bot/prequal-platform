"""Prometheus metrics instrumentation for analytics-service.

Self-contained observability module (DevOps: MID-591):
- HTTP request metrics via ASGI middleware (no coupling to business logic)
- Ingestion activity counter incremented from the middleware
- Redis stream backlog gauge polled by a background thread
- /metrics ASGI app mounted by main.py

Custom metrics exposed:
- analytics_events_ingested_total: successful ingestion/track requests
  (per-request granularity; batch sizes not reflected)
- analytics_redis_stream_backlog: XLEN of the analytics events stream
"""

import threading
import time
import logging

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    make_asgi_app,
)

logger = logging.getLogger(__name__)

REGISTRY = CollectorRegistry()

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    ["method", "status"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

analytics_events_ingested_total = Counter(
    "analytics_events_ingested_total",
    "Successful ingestion/track requests processed by the analytics service",
    registry=REGISTRY,
)

analytics_redis_stream_backlog = Gauge(
    "analytics_redis_stream_backlog",
    "Number of entries pending in the analytics events Redis stream",
    registry=REGISTRY,
)

INGESTION_PATH_SUFFIXES = (
    "/ingestion/events",
    "/ingestion/consume",
    "/track-feature",
    "/track-health",
)

METRICS_PATH = "/metrics"
BACKLOG_POLL_SECONDS = 30


class MetricsMiddleware:
    """ASGI middleware that records request count, duration, and ingestion activity."""

    async def __call__(self, request, call_next):
        if request.scope["path"] == METRICS_PATH:
            return await call_next(request)

        method = request.method
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            http_requests_total.labels(method=method, status=str(status)).inc()
            http_request_duration_seconds.labels(method=method).observe(duration)
            path = request.scope["path"]
            if (
                method == "POST"
                and 200 <= status < 300
                and path.endswith(INGESTION_PATH_SUFFIXES)
            ):
                analytics_events_ingested_total.inc()


def _poll_stream_backlog():
    """Poll the Redis stream length in a background thread (daemon)."""
    import redis as redis_lib

    from app.config import settings

    while True:
        try:
            client = redis_lib.Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            length = client.xlen(settings.ANALYTICS_EVENTS_STREAM)
            analytics_redis_stream_backlog.set(length)
        except Exception:
            logger.debug("Redis backlog poll failed; retrying")
        time.sleep(BACKLOG_POLL_SECONDS)


def start_backlog_poller():
    """Start the daemon backlog poller thread once."""
    thread = threading.Thread(target=_poll_stream_backlog, daemon=True)
    thread.start()


def create_metrics_asgi_app():
    """Create the /metrics ASGI app wired to the service registry."""
    return make_asgi_app(registry=REGISTRY)
