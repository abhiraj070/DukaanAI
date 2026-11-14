"""API v1 master router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    auth,
    documents,
    festivals,
    health,
    ingestion,
    inventory,
    optimization,
    simulation,
    udhar,
)

api_v1_router = APIRouter(prefix="/api/v1")

# Mount endpoints
api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(auth.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(ingestion.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(inventory.router)
api_v1_router.include_router(simulation.router)
api_v1_router.include_router(festivals.router)
api_v1_router.include_router(optimization.router)
api_v1_router.include_router(udhar.router)
