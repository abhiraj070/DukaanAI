"""Tests for /health and /api/v1/health endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health_returns_200(async_client: AsyncClient):
    """Test that GET /health returns 200 with expected fields and headers."""
    response = await async_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "DukaanAI"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"
    assert data["timezone"] == "Asia/Kolkata"
    assert "timestamp" in data

    # Verify request ID headers
    assert "x-request-id" in response.headers
    assert "x-process-time-ms" in response.headers
    assert data["request_id"] == response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_api_v1_health_returns_200(async_client: AsyncClient):
    """Test that GET /api/v1/health returns 200 with identical schema."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "DukaanAI"
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_request_id_propagation(async_client: AsyncClient):
    """Test that a client-provided X-Request-ID is preserved and echoed."""
    custom_req_id = "client-trace-12345"
    response = await async_client.get("/health", headers={"X-Request-ID": custom_req_id})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == custom_req_id
    data = response.json()
    assert data["request_id"] == custom_req_id
