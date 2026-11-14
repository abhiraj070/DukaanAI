"""Main FastAPI application entry point for DukaanAI."""

from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.health import HealthResponse
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIDMiddleware

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agentic Decision Intelligence Platform for Indian Small Businesses",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
)

# Request ID & Latency Middleware
app.add_middleware(RequestIDMiddleware)

# Standardized Error Handlers
register_error_handlers(app)


# Root-level health endpoint (for orchestration/health checks)
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def root_health(request: Request) -> HealthResponse:
    req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        timestamp=datetime.now(UTC),
        timezone=settings.DEFAULT_TIMEZONE,
        request_id=req_id,
    )


# Include v1 API router
app.include_router(api_v1_router)
