"""Health check endpoints for DukaanAI API."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """System health response model."""

    status: str = Field(default="ok", description="Service status indicator")
    app: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Running environment")
    timestamp: datetime = Field(..., description="Current UTC timestamp")
    timezone: str = Field(..., description="Default application business timezone")
    request_id: str | None = Field(default=None, description="Request ID for tracing")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health Check",
    description="Returns current operational status, version, and server timestamp.",
)
async def get_health(request: Request) -> HealthResponse:
    settings = get_settings()
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
