"""Hand-checked tests for SimulationService scenario projections and delta calculations."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.domain.festivals.service import FestivalIntelligenceService
from app.domain.simulation.service import SimulationService
from app.models.catalogue import Product
from app.models.operations import Sale, SaleItem
from app.models.simulation import ScenarioRun
from app.schemas.festivals import FestivalEventInput
from app.schemas.simulation import ScenarioItemInput, SimulationInput


def test_what_if_price_change_scenario(db_session: Session, tenants: dict):
    """Hand-checked verification of what-if price scenario delta calculations."""
    ctx_a = tenants["tenant_a"]["context"]

    # Create a product: selling 100.00, cost 80.00
    prod = Product(
        business_id=ctx_a.business_id,
        name="Cooking Oil 1L",
        selling_price=Decimal("100.00"),
        cost_price=Decimal("80.00"),
    )
    db_session.add(prod)
    db_session.flush()

    # Create sales: 30 units over 30-day window -> 1 unit/day
    sale = Sale(
        business_id=ctx_a.business_id,
        sale_number="BILL-SIM01",
        sold_at=datetime.now(UTC),
        total_amount=Decimal("3000.00"),
        status="COMPLETED",
    )
    db_session.add(sale)
    db_session.flush()

    item = SaleItem(
        business_id=ctx_a.business_id,
        sale_id=sale.id,
        product_id=prod.id,
        quantity=Decimal("30.000"),
        unit_price=Decimal("100.00"),
        unit_cost=Decimal("80.00"),
        total_amount=Decimal("3000.00"),
    )
    db_session.add(item)
    db_session.commit()

    service = SimulationService(db_session, ctx_a)

    # 30-day horizon simulation with +10% price change (price becomes 110.00)
    sim_input = SimulationInput(
        scenario_name="Test 10% Price Increase",
        time_horizon_days=30,
        items=[
            ScenarioItemInput(
                product_id=prod.id,
                price_delta_pct=Decimal("10.00"),
            )
        ],
        expected_udhar_collections=Decimal("2500.00"),
    )

    result = service.run_scenario(sim_input).data

    # Baseline: 30 units * 100 = 3,000.00; COGS = 30 * 80 = 2,400.00; Profit = 600.00
    assert result.revenue.baseline == Decimal("3000.00")
    assert result.cogs.baseline == Decimal("2400.00")
    assert result.gross_profit.baseline == Decimal("600.00")

    # Simulated: 30 units * 110 = 3,300.00; COGS = 2,400.00; Profit = 900.00
    assert result.revenue.simulated == Decimal("3300.00")
    assert result.revenue.delta_amount == Decimal("300.00")
    assert result.revenue.delta_pct == Decimal("10.00")

    assert result.gross_profit.simulated == Decimal("900.00")
    assert result.gross_profit.delta_amount == Decimal("300.00")
    assert result.gross_profit.delta_pct == Decimal("50.00")  # (300 / 600) * 100 = 50%

    # Cash collected estimate strictly preserved as scenario assumption
    assert result.cash_collected_estimate == Decimal("2500.00")
    assert any("Price elasticity assumed = 0" in a for a in result.assumptions_applied)
    saved = db_session.query(ScenarioRun).filter_by(business_id=ctx_a.business_id).one()
    assert saved.result_json["revenue"]["delta_amount"] == "300.00"
    assert len(service.list_scenarios()) == 1

    event = FestivalIntelligenceService(db_session, ctx_a).save_event(
        FestivalEventInput(
            name="Festival Scenario",
            region="Pune",
            start_date=datetime.now(UTC).date() + timedelta(days=20),
            end_date=datetime.now(UTC).date() + timedelta(days=22),
        )
    )
    festival_result = service.run_scenario(
        SimulationInput(
            scenario_name="Festival assumption",
            festival_event_id=event.id,
            festival_assumed_uplift_pct=Decimal("20"),
        )
    )
    assert festival_result.data.revenue.simulated == Decimal("3600.00")
    assert event.id in festival_result.evidence.source_record_ids


def test_what_if_discount_and_festival_demand_scenario(db_session: Session, tenants: dict):
    """Verify combination of general festival demand uplift and item-level discount."""
    ctx_a = tenants["tenant_a"]["context"]

    prod = Product(
        business_id=ctx_a.business_id,
        name="Basmati Rice 5kg",
        selling_price=Decimal("500.00"),
        cost_price=Decimal("400.00"),
    )
    db_session.add(prod)
    db_session.flush()

    sale = Sale(
        business_id=ctx_a.business_id,
        sale_number="BILL-SIM02",
        sold_at=datetime.now(UTC),
        total_amount=Decimal("15000.00"),
        status="COMPLETED",
    )
    db_session.add(sale)
    db_session.flush()

    item = SaleItem(
        business_id=ctx_a.business_id,
        sale_id=sale.id,
        product_id=prod.id,
        quantity=Decimal("30.000"),
        unit_price=Decimal("500.00"),
        unit_cost=Decimal("400.00"),
        total_amount=Decimal("15000.00"),
    )
    db_session.add(item)
    db_session.commit()

    service = SimulationService(db_session, ctx_a)

    # General demand uplift +20%, product discount -10% (price 450.00)
    # Units = 30 * 1.20 = 36.000 units
    # Revenue = 36 * 450.00 = 16,200.00 (baseline: 15,000.00) -> delta = +1,200.00 (+8%)
    # COGS = 36 * 400.00 = 14,400.00 (baseline: 12,000.00) -> delta = +2,400.00 (+20%)
    # Gross Profit = 16,200 - 14,400 = 1,800.00 (baseline: 3,000.00) -> delta = -1,200.00 (-40%)
    sim_input = SimulationInput(
        scenario_name="Diwali 10% Discount & 20% Demand Surge",
        time_horizon_days=30,
        general_demand_uplift_pct=Decimal("20.00"),
        items=[
            ScenarioItemInput(
                product_id=prod.id,
                price_delta_pct=Decimal("-10.00"),
            )
        ],
        purchase_cash_outflow=Decimal("12000.00"),
        supply_delay_days=5,
    )

    result = service.run_scenario(sim_input).data
    assert result.revenue.baseline == Decimal("15000.00")
    assert result.revenue.simulated == Decimal("16200.00")
    assert result.revenue.delta_amount == Decimal("1200.00")
    assert result.revenue.delta_pct == Decimal("8.00")

    assert result.cogs.baseline == Decimal("12000.00")
    assert result.cogs.simulated == Decimal("14400.00")
    assert result.cogs.delta_amount == Decimal("2400.00")

    assert result.gross_profit.baseline == Decimal("3000.00")
    assert result.gross_profit.simulated == Decimal("1800.00")
    assert result.gross_profit.delta_amount == Decimal("-1200.00")
    assert result.gross_profit.delta_pct == Decimal("-40.00")

    assert result.purchase_cash_outflow == Decimal("12000.00")
    assert result.supply_delay_days == 5


def test_invalid_scenario_inputs_are_rejected():
    with pytest.raises(ValidationError):
        SimulationInput(scenario_name="", general_demand_uplift_pct=0)
    with pytest.raises(ValidationError):
        SimulationInput(scenario_name="Invalid", general_demand_uplift_pct=-100)
    with pytest.raises(ValidationError):
        SimulationInput(
            scenario_name="Invalid price",
            items=[ScenarioItemInput(product_id="p1", price_delta_pct=-100)],
        )
    with pytest.raises(ValidationError):
        SimulationInput(
            scenario_name="Duplicate override",
            items=[ScenarioItemInput(product_id="p1"), ScenarioItemInput(product_id="p1")],
        )


def test_simulation_api_and_cross_tenant_isolation(client: TestClient, tenants: dict):
    """Test authenticated simulation endpoints and verify cross-tenant security."""
    user_a = tenants["tenant_a"]["user"]
    user_b = tenants["tenant_b"]["user"]
    prod_a = tenants["tenant_a"]["product"]
    prod_b = tenants["tenant_b"]["product"]

    token_a = create_access_token({"sub": user_a.id})
    token_b = create_access_token({"sub": user_b.id})

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Tenant A creates a scenario
    payload_a = {
        "scenario_name": "API Scenario A",
        "time_horizon_days": 14,
        "general_demand_uplift_pct": 10.0,
        "expected_udhar_collections": 1500.0,
        "items": [{"product_id": prod_a.id, "price_delta_pct": 5.0}],
    }
    resp = client.post("/api/v1/simulation/scenarios", json=payload_a, headers=headers_a)
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["scenario_name"] == "API Scenario A"
    assert res_data["cash_collected_estimate"] == "1500.00"

    # Tenant A lists scenarios
    list_a = client.get("/api/v1/simulation/scenarios", headers=headers_a)
    assert list_a.status_code == 200
    assert any(s["scenario_name"] == "API Scenario A" for s in list_a.json())

    # Tenant B lists scenarios -> cannot see Tenant A's scenario
    list_b = client.get("/api/v1/simulation/scenarios", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(s["scenario_name"] == "API Scenario A" for s in list_b.json())

    # Tenant A tries to include Tenant B's product -> 400 Bad Request
    payload_hack = {
        "scenario_name": "Cross Tenant Exploit",
        "time_horizon_days": 14,
        "items": [{"product_id": prod_b.id, "price_delta_pct": 10.0}],
    }
    resp_hack = client.post("/api/v1/simulation/scenarios", json=payload_hack, headers=headers_a)
    assert resp_hack.status_code == 400
    assert "outside the current business" in resp_hack.json()["error"]["message"]
