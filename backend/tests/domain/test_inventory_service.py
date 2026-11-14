"""Hand-checked tests for InventoryService formulas and supplier constraints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.domain.inventory.service import InventoryService
from app.models.catalogue import Product, SupplierProduct
from app.models.inventory import ForecastRun, MovementType
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
    # ROP = (2.000 * 3 lead_time) + 5 safety = 11.000
    result1 = service.forecast_demand(prod_a.id, horizon_days=14, history_days=30).data
    assert result1.historical_daily_demand == Decimal("2.000")
    assert result1.days_of_cover == Decimal("25.000")
    assert result1.reorder_point == Decimal("11.000")
    assert result1.is_reorder_recommended is False
    assert result1.suggested_order_qty == Decimal("0.000")
    festival_forecast = service.forecast_demand(
        prod_a.id,
        horizon_days=14,
        history_days=30,
        festival_uplift_pct=Decimal("20"),
        festival_source_ids=["festival-event"],
    )
    assert festival_forecast.data.forecast_demand_period == Decimal("33.600")
    assert "festival-event" in festival_forecast.evidence.source_record_ids

    # Case 2: Stock drops below ROP (dispatch 45 units -> stock = 5 units <= ROP 11)
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


def test_inventory_forecast_zero_demand_and_zero_stock(db_session: Session, tenants: dict):
    """Test forecast behavior with zero demand and zero stock."""
    ctx_a = tenants["tenant_a"]["context"]

    # Create a product with 0 stock and min_stock_level = 10
    prod = Product(
        business_id=ctx_a.business_id,
        name="Zero Stock Item",
        sku="ZSKU-001",
        unit="PCS",
        selling_price=Decimal("100.00"),
        cost_price=Decimal("70.00"),
        min_stock_level=Decimal("10.000"),
    )
    db_session.add(prod)
    db_session.commit()

    service = InventoryService(db_session, ctx_a)
    result = service.forecast_demand(prod.id, horizon_days=14, history_days=30).data

    assert result.forecast_method == "naive_zero_demand"
    assert result.historical_daily_demand == Decimal("0.000")
    assert result.forecast_demand_period == Decimal("0.000")
    assert result.days_of_cover is None
    assert result.data_quality == "NO_HISTORY"
    assert result.on_hand_stock == Decimal("0.000")
    # Stock (0) <= ROP (10) -> reorder recommended
    assert result.is_reorder_recommended is True
    assert result.suggested_order_qty == Decimal("10.000")  # covers safety stock
    assert result.estimated_cost == Decimal("700.00")  # 10 * 70


def test_inventory_forecast_sparse_and_rolling_methods(db_session: Session, tenants: dict):
    """Test method selection: sparse (<5 sales) vs rolling 7-day mean."""
    ctx_a = tenants["tenant_a"]["context"]

    prod = Product(
        business_id=ctx_a.business_id,
        name="Sparse Test Item",
        sku="SPARSE-001",
        unit="PCS",
        selling_price=Decimal("50.00"),
        cost_price=Decimal("35.00"),
        min_stock_level=Decimal("5.000"),
    )
    db_session.add(prod)
    db_session.flush()

    # Add 2 sales (sparse)
    now = datetime.now(UTC)
    for i in range(2):
        sale = Sale(
            business_id=ctx_a.business_id,
            sale_number=f"BILL-SPARSE-{i}",
            sold_at=now - timedelta(days=i + 1),
            total_amount=Decimal("100.00"),
            status="COMPLETED",
        )
        db_session.add(sale)
        db_session.flush()
        db_session.add(
            SaleItem(
                business_id=ctx_a.business_id,
                sale_id=sale.id,
                product_id=prod.id,
                quantity=Decimal("2.000"),
                unit_price=Decimal("50.00"),
                unit_cost=Decimal("35.00"),
                total_amount=Decimal("100.00"),
            )
        )
    db_session.commit()

    service = InventoryService(db_session, ctx_a)
    sparse_res = service.forecast_demand(prod.id, horizon_days=7, history_days=30).data
    assert sparse_res.data_quality == "SPARSE"
    assert sparse_res.forecast_method == "naive_history_mean"

    # Add 6 more sales to reach 8 total -> rolling 7 day mean
    for i in range(2, 8):
        sale = Sale(
            business_id=ctx_a.business_id,
            sale_number=f"BILL-ROLLING-{i}",
            sold_at=now - timedelta(days=i + 1),
            total_amount=Decimal("100.00"),
            status="COMPLETED",
        )
        db_session.add(sale)
        db_session.flush()
        db_session.add(
            SaleItem(
                business_id=ctx_a.business_id,
                sale_id=sale.id,
                product_id=prod.id,
                quantity=Decimal("2.000"),
                unit_price=Decimal("50.00"),
                unit_cost=Decimal("35.00"),
                total_amount=Decimal("100.00"),
            )
        )
    db_session.commit()

    rolling_res = service.forecast_demand(prod.id, horizon_days=7, history_days=30).data
    assert rolling_res.data_quality == "RELIABLE"
    assert rolling_res.forecast_method == "rolling_7_day_mean"

    # Verify ForecastRun was persisted
    runs = (
        db_session.query(ForecastRun)
        .filter(ForecastRun.business_id == ctx_a.business_id, ForecastRun.product_id == prod.id)
        .all()
    )
    assert len(runs) >= 2
    assert runs[-1].model_version == rolling_res.model_version
    assert runs[-1].forecast_method == "rolling_7_day_mean"


def test_inventory_forecast_api_and_cross_tenant_isolation(client: TestClient, tenants: dict):
    """Test authenticated forecast endpoint and verify Tenant B cannot query Tenant A's product."""
    user_a = tenants["tenant_a"]["user"]
    user_b = tenants["tenant_b"]["user"]
    prod_a = tenants["tenant_a"]["product"]

    token_a = create_access_token({"sub": user_a.id})
    token_b = create_access_token({"sub": user_b.id})

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Tenant A queries their own product forecast
    resp = client.get(f"/api/v1/inventory/products/{prod_a.id}/forecast", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["product_id"] == prod_a.id
    assert data["sku"] == prod_a.sku
    assert "model_version" in data

    # Tenant B tries to query Tenant A's product -> 404 Not Found (tenant-isolated)
    resp_b = client.get(f"/api/v1/inventory/products/{prod_a.id}/forecast", headers=headers_b)
    assert resp_b.status_code == 404
