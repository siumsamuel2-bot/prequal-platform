from contextlib import asynccontextmanager
import os
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import init_db, close_db
from app.routers import auth, compliance, alerts, credentials, analytics
from app.logging_config import setup_logging, get_logger


# Setup logging on module load
setup_logging("prequal-api")
logger = get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler with logging."""
    # Startup
    logger.info("Starting up Prequal API")
    await init_db()
    logger.info("Database connection established")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Prequal API")
    await close_db()
    logger.info("Database connection closed")


app = FastAPI(
    title="Prequal Compliance Platform API",
    description="API for tracking subcontractor compliance, certifications, and violations",
    version="1.0.0",
    lifespan=lifespan
)
app.state.limiter = limiter

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {request.method} {request.url.path} - {response.status_code}")
    return response


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


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

# Import and include health router (must be after app creation)
from api import health
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server")
    uvicorn.run(app, host="0.0.0.0", port=8000)