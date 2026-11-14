"""Hand-checked tests for SimulationService scenario projections and delta calculations."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.simulation.service import SimulationService
from app.models.catalogue import Product
from app.models.operations import Sale, SaleItem
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
