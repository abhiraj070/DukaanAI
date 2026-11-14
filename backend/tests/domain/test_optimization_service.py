"""Hand-checked tests for ProcurementOptimizerService budget constraints and ROI ranking."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.optimization.service import ProcurementOptimizerService
from app.models.catalogue import Product, Supplier, SupplierProduct
from app.models.operations import Sale, SaleItem
from app.schemas.optimization import OptimizationInput


def test_procurement_optimizer_strictly_respects_budget(db_session: Session, tenants: dict):
    """Verify that budget is never exceeded and items are prioritized by ROI."""
    ctx_a = tenants["tenant_a"]["context"]

    supplier = Supplier(business_id=ctx_a.business_id, name="Test Optimizer Supplier")
    db_session.add(supplier)
    db_session.flush()

    # Product High ROI (Cost 100, Selling 150 -> 50% ROI)
    p_high = Product(
        business_id=ctx_a.business_id,
        supplier_id=supplier.id,
        name="High Margin Biscuits",
        selling_price=Decimal("150.00"),
        cost_price=Decimal("100.00"),
        min_stock_level=Decimal("5.000"),
    )
    # Product Medium ROI (Cost 200, Selling 250 -> 25% ROI)
    p_med = Product(
        business_id=ctx_a.business_id,
        supplier_id=supplier.id,
        name="Medium Margin Detergent",
        selling_price=Decimal("250.00"),
        cost_price=Decimal("200.00"),
        min_stock_level=Decimal("5.000"),
    )
    # Product Expensive Low ROI (Cost 500, Selling 550 -> 10% ROI)
    p_low = Product(
        business_id=ctx_a.business_id,
        supplier_id=supplier.id,
        name="Expensive Olive Oil",
        selling_price=Decimal("550.00"),
        cost_price=Decimal("500.00"),
        min_stock_level=Decimal("5.000"),
    )
    db_session.add_all([p_high, p_med, p_low])
    db_session.flush()

    # Supplier constraints: MOQ = 10, Pack Size = 5
    for p in [p_high, p_med, p_low]:
        sp = SupplierProduct(
            business_id=ctx_a.business_id,
            supplier_id=supplier.id,
            product_id=p.id,
            purchase_cost=p.cost_price,
            moq=Decimal("10.000"),
            pack_size=Decimal("5.000"),
        )
        db_session.add(sp)

    # Record historical sales over 30 days:
    # 60 units of each sold -> 2 units/day
    sale = Sale(
        business_id=ctx_a.business_id,
        sale_number="BILL-OPT01",
        sold_at=datetime.now(UTC),
        total_amount=Decimal("57000.00"),
        status="COMPLETED",
    )
    db_session.add(sale)
    db_session.flush()

    for p in [p_high, p_med, p_low]:
        item = SaleItem(
            business_id=ctx_a.business_id,
            sale_id=sale.id,
            product_id=p.id,
            quantity=Decimal("60.000"),
            unit_price=p.selling_price,
            unit_cost=p.cost_price,
            total_amount=Decimal("60.000") * p.selling_price,
        )
        db_session.add(item)

    db_session.commit()

    service = ProcurementOptimizerService(db_session, ctx_a)

    # Budget = ₹10,000. Horizon = 10 days.
    # Target stock = (2 units/day * 10 days) + 5 safety = 25 units.
    # On-hand = 0 -> Net need = 25 units (multiple of 5 pack size).
    #
    # Costs:
    # High: 25 * 100 = ₹2,500 (Profit: 25 * 50 = ₹1,250 -> 50% ROI)
    # Med:  25 * 200 = ₹5,000 (Profit: 25 * 50 = ₹1,250 -> 25% ROI)
    # Low:  25 * 500 = ₹12,500 (Profit: 25 * 50 = ₹1,250 -> 10% ROI)
    #
    # Under budget ₹10,000:
    # 1. Takes High: cost ₹2,500, remaining budget = ₹7,500.
    # 2. Takes Med:  cost ₹5,000, remaining budget = ₹2,500.
    # 3. Low costs ₹12,500 > ₹2,500 -> cannot fit!
    # Total allocated = ₹7,500 <= ₹10,000. Remaining = ₹2,500.

    opt_input = OptimizationInput(
        budget_inr=Decimal("10000.00"),
        planning_horizon_days=10,
    )
    result = service.optimize_procurement(opt_input).data

    assert result.budget_allocated == Decimal("7500.00")
    assert result.budget_remaining == Decimal("2500.00")
    assert result.budget_allocated <= Decimal("10000.00")  # INVARIANT: never exceeds budget!

    rec_names = [r.product_name for r in result.recommendations]
    assert "High Margin Biscuits" in rec_names
    assert "Medium Margin Detergent" in rec_names
    assert "Expensive Olive Oil" not in rec_names

    # Check pack size and MOQ applied
    for r in result.recommendations:
        assert r.order_quantity == Decimal("25.000")
        assert r.order_quantity >= r.moq_applied
        assert r.order_quantity % r.pack_size_applied == Decimal("0.000")
