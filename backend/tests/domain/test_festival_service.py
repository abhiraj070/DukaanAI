"""Festival calendar tenant scoping and seasonal uplift evidence tests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NotFoundError
from app.core.security import create_access_token
from app.domain.festivals.service import FestivalIntelligenceService
from app.models.operations import Sale, SaleItem
from app.schemas.festivals import FestivalEventInput


def test_insufficient_festival_history_uses_labeled_user_assumption(db_session, tenants):
    ctx = tenants["tenant_a"]["context"]
    service = FestivalIntelligenceService(db_session, ctx)
    event = service.save_event(
        FestivalEventInput(
            name="Local Fair",
            region="Pune",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 2),
        )
    )
    result = service.estimate_uplift(event.id, Decimal("18"))

    assert result.data.quality == "USER_ASSUMPTION"
    assert result.data.observed_uplift_pct is None
    assert result.data.planning_uplift_pct == Decimal("18.00")
    assert result.evidence.source_record_ids == [event.id]

    with pytest.raises(NotFoundError):
        FestivalIntelligenceService(db_session, tenants["tenant_b"]["context"]).estimate_uplift(
            event.id
        )


def test_historical_uplift_requires_and_averages_two_comparable_occurrences(db_session, tenants):
    ctx = tenants["tenant_a"]["context"]
    product = tenants["tenant_a"]["product"]
    service = FestivalIntelligenceService(db_session, ctx)
    upcoming = service.save_event(
        FestivalEventInput(
            name="Harvest Day",
            region="Pune",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 3),
        )
    )
    prior_dates = [(date(2024, 10, 1), date(2024, 10, 3)), (date(2025, 10, 1), date(2025, 10, 3))]
    for occurrence, (start, end) in enumerate(prior_dates):
        service.save_event(
            FestivalEventInput(name="Harvest Day", region="Pune", start_date=start, end_date=end)
        )
        for is_festival, _offset, quantity in [(False, 0, Decimal("10")), (True, 0, Decimal("30"))]:
            base = start if is_festival else start - timedelta(days=28)
            for index in range(5):
                sale_date = base + timedelta(days=(index % 3 if is_festival else index))
                sold_at = datetime.combine(sale_date, datetime.min.time(), tzinfo=UTC)
                sale = Sale(
                    business_id=ctx.business_id,
                    sale_number=f"FEST-{occurrence}-{is_festival}-{index}",
                    sold_at=sold_at,
                    total_amount=Decimal("100.00"),
                    status="COMPLETED",
                )
                db_session.add(sale)
                db_session.flush()
                db_session.add(
                    SaleItem(
                        business_id=ctx.business_id,
                        sale_id=sale.id,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=Decimal("10.00"),
                        unit_cost=Decimal("5.00"),
                        total_amount=quantity * Decimal("10.00"),
                    )
                )
    db_session.commit()

    result = service.estimate_uplift(upcoming.id)
    assert result.data.quality == "HISTORICAL"
    assert result.data.comparable_occurrences == 2
    assert result.data.observed_uplift_pct is not None
    assert result.data.observed_uplift_pct > Decimal("100")


def test_festival_api_and_cross_tenant_isolation(client: TestClient, tenants: dict):
    """Test authenticated festival endpoints and cross-tenant isolation."""
    user_a = tenants["tenant_a"]["user"]
    user_b = tenants["tenant_b"]["user"]

    token_a = create_access_token({"sub": user_a.id})
    token_b = create_access_token({"sub": user_b.id})

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Tenant A creates an event
    payload = {
        "name": "Diwali Bazaar 2026",
        "region": "Mumbai",
        "start_date": "2026-11-01",
        "end_date": "2026-11-05",
    }
    resp = client.post("/api/v1/festivals/calendar", json=payload, headers=headers_a)
    assert resp.status_code == 200
    event_a = resp.json()
    assert event_a["name"] == "Diwali Bazaar 2026"
    event_id = event_a["id"]

    # Tenant A lists events -> includes Diwali Bazaar 2026
    list_a = client.get("/api/v1/festivals/calendar", headers=headers_a)
    assert list_a.status_code == 200
    assert any(e["id"] == event_id for e in list_a.json())

    # Tenant B lists events -> does NOT include Tenant A's event
    list_b = client.get("/api/v1/festivals/calendar", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(e["id"] == event_id for e in list_b.json())

    # Tenant B tries to query uplift for Tenant A's event -> 404
    resp_b = client.get(f"/api/v1/festivals/calendar/{event_id}/uplift", headers=headers_b)
    assert resp_b.status_code == 404
