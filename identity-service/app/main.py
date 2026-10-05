from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """Middleware that adds security headers to all responses."""

    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Prequal Identity Service")
    yield
    logger.info("Shutting down Prequal Identity Service")


app = FastAPI(
    title="Prequal Identity Service",
    description="Authentication and user management microservice for Prequal platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "prequal-identity-service"}


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server on 0.0.0.0:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)