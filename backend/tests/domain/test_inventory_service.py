"""Hand-checked tests for InventoryService formulas and supplier constraints."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.inventory.service import InventoryService
from app.models.catalogue import SupplierProduct
from app.models.inventory import MovementType
from app.models.operations import Sale, SaleItem
from app.repositories.inventory import InventoryRepository


def test_inventory_forecast_and_reorder_formulas(db_session: Session, tenants: dict):
    """Hand-checked verification of days of cover, ROP, and pack-size/MOQ rounding."""
    ctx_a = tenants["tenant_a"]["context"]
    prod_a = tenants["tenant_a"]["product"]  # initial stock from fixture: 25.000

    inv_repo = InventoryRepository(db_session, ctx_a)

    # Bring on-hand stock to 50.000
    inv_repo.record_movement(
        product_id=prod_a.id,
        movement_type=MovementType.PURCHASE_RECEIPT,
        quantity=Decimal("25.000"),
    )
    assert inv_repo.get_stock(prod_a.id) == Decimal("50.000")

    # Record 60 units sold over the past 30 days -> daily demand = 60 / 30 = 2.000 units/day
    sale = Sale(
        business_id=ctx_a.business_id,
        sale_number="BILL-F01",
        sold_at=datetime.now(UTC),
        total_amount=Decimal("27000.00"),
        status="COMPLETED",
    )
    db_session.add(sale)
    db_session.flush()

    item = SaleItem(
        business_id=ctx_a.business_id,
        sale_id=sale.id,
        product_id=prod_a.id,
        quantity=Decimal("60.000"),
        unit_price=Decimal("450.00"),
        unit_cost=Decimal("380.00"),
        total_amount=Decimal("27000.00"),
    )
    db_session.add(item)

    # Configure supplier link with MOQ = 20, Pack Size = 10, Purchase Cost = 380.00
    supp_link = SupplierProduct(
        business_id=ctx_a.business_id,
        supplier_id=prod_a.supplier_id,
        product_id=prod_a.id,
        purchase_cost=Decimal("380.00"),
        moq=Decimal("20.000"),
        pack_size=Decimal("10.000"),
        lead_time_days=3,
    )
    db_session.add(supp_link)
    db_session.commit()

    service = InventoryService(db_session, ctx_a)

    # Case 1: Ample stock (50 units)
    # daily_demand = 60 / 30 = 2.000
    # days_of_cover = 50 / 2 = 25.000 days
    # ROP = (2.000 * 2 lead_time) + 5 safety = 9.000
    result1 = service.forecast_demand(prod_a.id, horizon_days=14, history_days=30).data
    assert result1.historical_daily_demand == Decimal("2.000")
    assert result1.days_of_cover == Decimal("25.000")
    assert result1.reorder_point == Decimal("9.000")  # supplier lead time = 2 days from fixture
    assert result1.is_reorder_recommended is False
    assert result1.suggested_order_qty == Decimal("0.000")

    # Case 2: Stock drops below ROP (dispatch 45 units -> stock = 5 units <= ROP 9)
    inv_repo.record_movement(
        product_id=prod_a.id,
        movement_type=MovementType.SALE_DISPATCH,
        quantity=Decimal("45.000"),
    )
    assert inv_repo.get_stock(prod_a.id) == Decimal("5.000")

    # Target coverage = (2.000 * 14) + 5 safety = 28 + 5 = 33 units
    # Net raw need = 33 - 5 on hand = 28 units
    # Pack size = 10 -> ceil(28 / 10) = 3 -> 3 * 10 = 30 units (>= MOQ 20)
    result2 = service.forecast_demand(prod_a.id, horizon_days=14, history_days=30).data
    assert result2.is_reorder_recommended is True
    assert result2.suggested_order_qty == Decimal("30.000")
    assert result2.estimated_cost == Decimal("11400.00")  # 30 * 380.00
