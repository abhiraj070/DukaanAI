"""Tests for Phase 4 Core Business Analytics domain service, endpoints, and invariants."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.domain.analytics.date_ranges import resolve_date_window
from app.domain.analytics.service import AnalyticsService
from app.models.operations import Sale, SaleItem


def auth_headers(user_id: str) -> dict[str, str]:
    """Helper to generate JWT Bearer auth headers for testing."""
    token = create_access_token({"sub": user_id})
    return {"Authorization": f"Bearer {token}"}


# -------------------------------------------------------------------------
# 1. Unit & Edge-Case Tests: Returns, Empty Data, Missing Costs, Timezones
# -------------------------------------------------------------------------


def test_analytics_empty_data_returns_zero_without_error(db_session: Session, tenants: dict):
    """When a store has no sales or expenses, analytics returns clean 0.00 without crashing."""
    ctx_b = tenants["tenant_b"]["context"]
    service = AnalyticsService(db_session, ctx_b)

    result = service.get_kpis()
    kpis = result.data

    assert kpis.gross_revenue == Decimal("0.00")
    assert kpis.sales_returns == Decimal("0.00")
    assert kpis.net_revenue == Decimal("0.00")
    assert kpis.total_units_sold == Decimal("0.000")
    assert kpis.transaction_count == 0
    assert kpis.total_expenses == Decimal("0.00")
    assert kpis.cost_data_available is True
    # Profit is 0.00 (not None, because no items had missing costs)
    assert kpis.gross_profit == Decimal("0.00")
    assert kpis.gross_margin_pct == Decimal("0.00")


def test_sales_returns_deduct_from_gross_revenue(db_session: Session, tenants: dict):
    """Returned sales deduct from gross revenue to yield net revenue and reduce gross profit."""
    ctx_a = tenants["tenant_a"]["context"]
    prod_a = tenants["tenant_a"]["product"]  # selling: 450.00, cost: 380.00

    now = datetime.now(UTC)

    # Completed sale: 2 units @ 450.00 = 900.00 (cost: 760.00)
    sale1 = Sale(
        business_id=ctx_a.business_id,
        sale_number="S-COMP-01",
        sold_at=now,
        total_amount=Decimal("900.00"),
        status="COMPLETED",
    )
    db_session.add(sale1)
    db_session.flush()

    item1 = SaleItem(
        business_id=ctx_a.business_id,
        sale_id=sale1.id,
        product_id=prod_a.id,
        quantity=Decimal("2.000"),
        unit_price=Decimal("450.00"),
        unit_cost=Decimal("380.00"),
        total_amount=Decimal("900.00"),
    )
    db_session.add(item1)

    # Returned sale: 1 unit returned for 450.00 refund
    sale_ret = Sale(
        business_id=ctx_a.business_id,
        sale_number="S-RET-01",
        sold_at=now,
        total_amount=Decimal("450.00"),
        status="RETURNED",
    )
    db_session.add(sale_ret)
    db_session.commit()

    service = AnalyticsService(db_session, ctx_a)
    result = service.get_kpis()
    kpis = result.data

    assert kpis.gross_revenue == Decimal("900.00")
    assert kpis.sales_returns == Decimal("450.00")
    # Net revenue = 900.00 - 450.00 = 450.00
    assert kpis.net_revenue == Decimal("450.00")
    # COGS = 760.00 (cost of 2 dispatched items)
    assert kpis.cogs == Decimal("760.00")
    # Gross Profit = Net Revenue (450.00) - COGS (760.00) = -310.00
    assert kpis.gross_profit == Decimal("-310.00")


def test_date_boundary_resolution_kolkata_timezone():
    """Verify Asia/Kolkata date windows resolve correctly to UTC boundaries."""
    s_utc, e_utc, label = resolve_date_window("TODAY", tz_name="Asia/Kolkata")
    assert label == "TODAY"
    assert s_utc is not None and e_utc is not None
    assert s_utc.tzinfo == UTC
    assert e_utc.tzinfo == UTC

    # Difference between start and end of a single day is exactly ~24 hours
    diff = e_utc - s_utc
    assert diff.total_seconds() > 86390 and diff.total_seconds() <= 86400

    # Test ALL_TIME returns None bounds
    s_all, e_all, label_all = resolve_date_window("ALL_TIME")
    assert s_all is None
    assert e_all is None
    assert label_all == "ALL_TIME"


# -------------------------------------------------------------------------
# 2. Integration Tests: API Endpoints, Evidence Envelopes, Isolation
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kpi_overview_api_endpoint(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """GET /api/v1/analytics/kpis returns typed DomainResult with evidence metadata."""
    user_a = tenants["tenant_a"]["user"]
    ctx_a = tenants["tenant_a"]["context"]
    prod_a = tenants["tenant_a"]["product"]
    headers = auth_headers(user_a.id)

    # Insert a sale for Tenant A
    sale = Sale(
        business_id=ctx_a.business_id,
        sale_number="API-SALE-01",
        sold_at=datetime.now(UTC),
        total_amount=Decimal("1350.00"),
        status="COMPLETED",
    )
    db_session.add(sale)
    db_session.flush()

    item = SaleItem(
        business_id=ctx_a.business_id,
        sale_id=sale.id,
        product_id=prod_a.id,
        quantity=Decimal("3.000"),
        unit_price=Decimal("450.00"),
        unit_cost=Decimal("380.00"),
        total_amount=Decimal("1350.00"),
    )
    db_session.add(item)
    db_session.commit()

    response = await async_client.get(
        "/api/v1/analytics/kpis?period=ALL_TIME",
        headers=headers,
    )
    assert response.status_code == 200
    res = response.json()

    assert "data" in res
    assert "evidence" in res

    data = res["data"]
    assert data["gross_revenue"] == "1350.00"
    assert data["net_revenue"] == "1350.00"
    assert data["cogs"] == "1140.00"  # 3 * 380.00
    assert data["gross_profit"] == "210.00"  # 1350.00 - 1140.00
    assert data["total_units_sold"] == "3.000"
    assert data["transaction_count"] == 1
    assert data["cost_data_available"] is True

    # Evidence envelope verification
    evidence = res["evidence"]
    assert "deterministic_sales_aggregation" in evidence["calculation_method"]
    assert sale.id in evidence["source_record_ids"]
    assert "freshness_timestamp" in evidence


@pytest.mark.asyncio
async def test_product_rankings_api_endpoint(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """GET /api/v1/analytics/products returns top products and slow movers."""
    user_a = tenants["tenant_a"]["user"]
    headers = auth_headers(user_a.id)

    # Query product rankings
    response = await async_client.get(
        "/api/v1/analytics/products?period=ALL_TIME",
        headers=headers,
    )
    assert response.status_code == 200
    res = response.json()

    assert "data" in res
    data = res["data"]
    assert "top_by_revenue" in data
    assert "top_by_units" in data
    assert "top_by_profit" in data
    assert "slow_moving" in data


@pytest.mark.asyncio
async def test_category_breakdown_api_endpoint(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """GET /api/v1/analytics/categories returns category sales and margins."""
    user_a = tenants["tenant_a"]["user"]
    headers = auth_headers(user_a.id)

    response = await async_client.get(
        "/api/v1/analytics/categories?period=ALL_TIME",
        headers=headers,
    )
    assert response.status_code == 200
    res = response.json()
    assert "categories" in res["data"]
    assert "total_revenue" in res["data"]


@pytest.mark.asyncio
async def test_analytics_trends_api_endpoint(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """GET /api/v1/analytics/trends returns daily data points for charts."""
    user_a = tenants["tenant_a"]["user"]
    headers = auth_headers(user_a.id)

    response = await async_client.get(
        "/api/v1/analytics/trends?period=LAST_30_DAYS",
        headers=headers,
    )
    assert response.status_code == 200
    res = response.json()
    assert "points" in res["data"]
    assert "total_revenue" in res["data"]


@pytest.mark.asyncio
async def test_cross_tenant_analytics_isolation(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """Verify Tenant B cannot see Tenant A's sales, revenue, or analytics."""
    user_b = tenants["tenant_b"]["user"]
    ctx_a = tenants["tenant_a"]["context"]
    headers_b = auth_headers(user_b.id)

    # Insert high-value sale for Tenant A
    sale_a = Sale(
        business_id=ctx_a.business_id,
        sale_number="TENANT-A-SECRET-01",
        sold_at=datetime.now(UTC),
        total_amount=Decimal("99999.00"),
        status="COMPLETED",
    )
    db_session.add(sale_a)
    db_session.commit()

    # Tenant B queries KPIs: must NOT see Tenant A's ₹99,999 sale!
    res_b = await async_client.get("/api/v1/analytics/kpis?period=ALL_TIME", headers=headers_b)
    assert res_b.status_code == 200
    b_data = res_b.json()["data"]

    assert Decimal(b_data["gross_revenue"]) < Decimal("99999.00")
    # Verify Tenant A's sale ID is not in Tenant B's evidence
    assert sale_a.id not in res_b.json()["evidence"]["source_record_ids"]
