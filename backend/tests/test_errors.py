"""Tests for standardized API error handling and request ID preservation."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_404_not_found_envelope(async_client: AsyncClient):
    """Test that querying a non-existent route returns our standardized error envelope."""
    response = await async_client.get("/non-existent-route")
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "NOT_FOUND"
    assert "message" in error
    assert "request_id" in error
    assert "x-request-id" in response.headers
    assert error["request_id"] == response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_404_preserves_custom_request_id(async_client: AsyncClient):
    """Test that 404 responses preserve an incoming X-Request-ID."""
    custom_id = "trace-404-check"
    response = await async_client.get(
        "/another-missing-route",
        headers={"X-Request-ID": custom_id},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["request_id"] == custom_id
    assert response.headers["x-request-id"] == custom_id
