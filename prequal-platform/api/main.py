from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import init_db, close_db, engine
from app.routers import auth, compliance, alerts, credentials, analytics, webhooks, billing, state_compliance
from app.logging_config import setup_logging, get_logger
from app.middleware.rate_limit import setup_rate_limiting
from app.middleware.correlation_id import setup_correlation_id
from app.metrics import setup_metrics, update_db_pool_metrics, PROMETHEUS_AVAILABLE


setup_logging("prequal-api")
logger = get_logger(__name__)


async def _update_db_pool_metrics_loop():
    """Background loop to update database connection pool metrics every 15s."""
    while True:
        try:
            sync_engine = engine.sync_engine
            pool = sync_engine.pool
            active = pool.size() - pool.available()
            max_conns = pool.size() + pool.overflow()
            update_db_pool_metrics(active, max_conns)
        except Exception as e:
            logger.debug(f"Could not update db pool metrics: {e}")
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler with logging."""
    logger.info("Starting up Prequal API")
    await init_db()
    logger.info("Database connection established")

    if PROMETHEUS_AVAILABLE:
        asyncio.create_task(_update_db_pool_metrics_loop())
        logger.info("Database pool metrics collection started")

    yield

    logger.info("Shutting down Prequal API")
    await close_db()
    logger.info("Database connection closed")


app = FastAPI(
    title="Prequal Compliance Platform API",
    description="API for tracking subcontractor compliance, certifications, and violations",
    version="1.0.0",
    lifespan=lifespan
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with correlation ID."""
    from app.middleware.correlation_id import get_correlation_id
    request_id = get_correlation_id()
    logger.info(f"Request: {request.method} {request.url.path} [request_id={request_id}]")
    response = await call_next(request)
    logger.info(f"Response: {request.method} {request.url.path} - {response.status_code} [request_id={request_id}]")
    return response


# Middleware wiring MUST happen at import time: calling app.add_middleware
# after the application has started raises RuntimeError. Stack order
# (outermost last): CORS -> correlation ID -> rate limiting -> metrics.
if PROMETHEUS_AVAILABLE:
    setup_metrics(app)
    logger.info("Prometheus metrics endpoint enabled at /metrics")

setup_rate_limiting(app)
setup_correlation_id(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count"],
)

# Health check endpoints
app.include_router(auth.router)
app.include_router(compliance.router)
app.include_router(alerts.router)
app.include_router(credentials.router)
app.include_router(analytics.router)
app.include_router(webhooks.router)
app.include_router(billing.router)
app.include_router(state_compliance.router)

# Import and include health router (must be after app creation)
from api import health
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server")
    uvicorn.run(app, host="0.0.0.0", port=8000)