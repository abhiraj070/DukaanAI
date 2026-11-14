"""Hand-checked tests for AnalyticsService calculations and invariants."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.analytics.service import AnalyticsService
from app.models.catalogue import Product
from app.models.operations import Expense, Sale, SaleItem


def test_kpi_overview_hand_checked_formulas(db_session: Session, tenants: dict):
    """Hand-checked verification of revenue, COGS, gross profit, and margin formulas."""
    ctx_a = tenants["tenant_a"]["context"]
    prod_a = tenants["tenant_a"]["product"]  # selling: 450.00, cost: 380.00

    # 1. Create 2 completed sales
    # Sale 1: 10 units @ 450.00 = 4,500.00 (COGS: 10 * 380.00 = 3,800.00)
    sale1 = Sale(
        business_id=ctx_a.business_id,
        sale_number="BILL-H01",
        sold_at=datetime.now(UTC),
        total_amount=Decimal("4500.00"),
        payment_mode="CASH",
        status="COMPLETED",
    )
    db_session.add(sale1)
    db_session.flush()

    item1 = SaleItem(
        business_id=ctx_a.business_id,
        sale_id=sale1.id,
        product_id=prod_a.id,
        quantity=Decimal("10.000"),
        unit_price=Decimal("450.00"),
        unit_cost=Decimal("380.00"),
        total_amount=Decimal("4500.00"),
    )
    db_session.add(item1)

    # Sale 2: 5 units @ 450.00 = 2,250.00 (COGS: 5 * 380.00 = 1,900.00)
    sale2 = Sale(
        business_id=ctx_a.business_id,
        sale_number="BILL-H02",
        sold_at=datetime.now(UTC),
        total_amount=Decimal("2250.00"),
        payment_mode="UPI",
        status="COMPLETED",
    )
    db_session.add(sale2)
    db_session.flush()

    item2 = SaleItem(
        business_id=ctx_a.business_id,
        sale_id=sale2.id,
        product_id=prod_a.id,
        quantity=Decimal("5.000"),
        unit_price=Decimal("450.00"),
        unit_cost=Decimal("380.00"),
        total_amount=Decimal("2250.00"),
    )
    db_session.add(item2)

    # Expense: Shop Electricity ₹650.00
    expense = Expense(
        business_id=ctx_a.business_id,
        category="UTILITIES",
        amount=Decimal("650.00"),
        expense_date=datetime.now(UTC),
    )
    db_session.add(expense)
    db_session.commit()

    service = AnalyticsService(db_session, ctx_a)
    result = service.get_kpis()
    kpis = result.data

    # Hand-checked assertions:
    # Gross Revenue = 4,500.00 + 2,250.00 = 6,750.00
    assert kpis.gross_revenue == Decimal("6750.00")

    # COGS = 3,800.00 + 1,900.00 = 5,700.00
    assert kpis.cogs == Decimal("5700.00")

    # Gross Profit = 6,750.00 - 5,700.00 = 1,050.00
    assert kpis.gross_profit == Decimal("1050.00")

    # Gross Margin % = (1,050.00 / 6,750.00) * 100 = 15.5555... -> 15.56%
    assert kpis.gross_margin_pct == Decimal("15.56")

    # Units = 15.000
    assert kpis.total_units_sold == Decimal("15.000")
    assert kpis.transaction_count == 2
    assert kpis.total_expenses == Decimal("650.00")
    assert kpis.cost_data_available is True

    # Evidence transparency
    assert len(result.evidence.source_record_ids) == 2
    assert "deterministic_sales_aggregation" in result.evidence.calculation_method


def test_missing_cost_price_makes_profit_unavailable(db_session: Session, tenants: dict):
    """If product cost is missing, profit is unavailable (None), never guessed as zero."""
    ctx_a = tenants["tenant_a"]["context"]

    # Create product without cost price
    prod_no_cost = Product(
        business_id=ctx_a.business_id,
        name="Mystery Spice Mix",
        selling_price=Decimal("150.00"),
        cost_price=None,  # Missing cost!
    )
    db_session.add(prod_no_cost)
    db_session.flush()

    sale = Sale(
        business_id=ctx_a.business_id,
        sale_number="BILL-NOCOST-01",
        total_amount=Decimal("300.00"),
        status="COMPLETED",
    )
    db_session.add(sale)
    db_session.flush()

    item = SaleItem(
        business_id=ctx_a.business_id,
        sale_id=sale.id,
        product_id=prod_no_cost.id,
        quantity=Decimal("2.000"),
        unit_price=Decimal("150.00"),
        unit_cost=None,  # Unknown
        total_amount=Decimal("300.00"),
    )
    db_session.add(item)
    db_session.commit()

    service = AnalyticsService(db_session, ctx_a)
    result = service.get_kpis()
    kpis = result.data

    assert kpis.gross_revenue == Decimal("300.00")
    # Invariant: Never report gross_profit as 300.00 (revenue is not profit!) or 0.00
    assert kpis.cogs is None
    assert kpis.gross_profit is None
    assert kpis.gross_margin_pct is None
    assert kpis.cost_data_available is False
    assert len(result.evidence.warnings) > 0
