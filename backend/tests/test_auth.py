"""Tests for authentication and demo session endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session


@pytest.mark.asyncio
async def test_demo_token_and_login_flow(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """Verify demo token retrieval and login flow."""
    # 1. Get demo token
    demo_res = await async_client.post("/api/v1/auth/demo-token")
    assert demo_res.status_code == 200
    demo_data = demo_res.json()
    assert "access_token" in demo_data
    assert demo_data["token_type"] == "bearer"
    assert demo_data["full_name"] == "Rajesh Sharma"

    # 2. Login with valid credentials
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "sharma@sharmakirana.test", "password": "Kirana@12345"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_data["business_name"] == "Sharma Kirana Store"

    # 3. Login with invalid password fails with 401
    bad_login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "sharma@sharmakirana.test", "password": "WrongPassword"},
    )
    assert bad_login_res.status_code == 401
