"""
Prometheus metrics instrumentation for Prequal Platform FastAPI application.

Add to your FastAPI app to expose /metrics endpoint for Prometheus scraping.
"""

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
import time
import logging
from typing import Callable

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        multiprocess,
        start_http_server,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed. Metrics will not be available.")

if PROMETHEUS_AVAILABLE:
    REQUEST_COUNT = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )

    REQUEST_LATENCY = Histogram(
        'http_request_duration_seconds',
        'HTTP request latency in seconds',
        ['method', 'endpoint'],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
    )

    REQUESTS_IN_PROGRESS = Gauge(
        'http_requests_in_progress',
        'Number of HTTP requests currently being processed',
        ['method', 'endpoint']
    )

    DB_POOL_ACTIVE = Gauge(
        'db_pool_active_connections',
        'Number of active database connections in the pool'
    )

    DB_POOL_MAX = Gauge(
        'db_pool_max_connections',
        'Maximum number of database connections in the pool'
    )

    RATE_LIMIT_HITS = Counter(
        'rate_limit_hits_total',
        'Total number of rate limit exceeded events',
        ['endpoint']
    )

    RATE_LIMIT_BLOCKED_IPS = Gauge(
        'rate_limit_blocked_ips',
        'Number of currently blocked IP addresses'
    )


_METRICS_SETUP_DONE = False


def setup_metrics(app: FastAPI):
    """
    Set up Prometheus metrics collection for a FastAPI application.
    
    This adds:
    - /metrics endpoint for Prometheus scraping
    - Request counting middleware
    - Latency tracking
    - In-progress request gauge
    
    Idempotent: safe to call multiple times on the same app.
    
    Usage:
        from app.metrics import setup_metrics
        app = FastAPI()
        setup_metrics(app)
    """
    global _METRICS_SETUP_DONE
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Skipping metrics setup - prometheus_client not available")
        return
    if _METRICS_SETUP_DONE:
        return
    _METRICS_SETUP_DONE = True

    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheus metrics endpoint."""
        return PlainTextResponse(
            generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Callable):
        """Middleware to collect HTTP request metrics."""
        start_time = time.time()
        
        # Track in-progress requests
        endpoint = request.url.path
        method = request.method
        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        
        try:
            response = await call_next(request)

            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status=response.status_code
            ).inc()

            if response.status_code == 429:
                RATE_LIMIT_HITS.labels(endpoint=endpoint).inc()

            duration = time.time() - start_time
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

            return response
        finally:
            REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()


def update_db_pool_metrics(active_connections: int, max_connections: int):
    """
    Update database connection pool metrics.
    
    Call this when your application updates its connection pool state.
    
    Args:
        active_connections: Current number of active connections
        max_connections: Maximum pool size
    """
    if PROMETHEUS_AVAILABLE:
        DB_POOL_ACTIVE.set(active_connections)
        DB_POOL_MAX.set(max_connections)


def start_metrics_server(port: int = 8001):
    """
    Start a standalone Prometheus metrics HTTP server.
    
    This is useful if you want to serve metrics on a separate port
    from your main application.
    
    Args:
        port: Port number for the metrics server
    """
    if PROMETHEUS_AVAILABLE:
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")