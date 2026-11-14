"""Tests for inventory movements, stock reconciliation, and Decimal precision."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, NotFoundError
from app.models.inventory import MovementType
from app.repositories.inventory import InventoryRepository
from app.repositories.product import ProductRepository


def test_inventory_reconciles_to_movements(db_session: Session, tenants: dict):
    """Verify that stock levels reconcile strictly to the sum of inventory movements."""
    ctx_a = tenants["tenant_a"]["context"]
    prod_a = tenants["tenant_a"]["product"]

    inv_repo = InventoryRepository(db_session, ctx_a)
    prod_repo = ProductRepository(db_session, ctx_a)

    # Initial stock from fixture is 25.000
    assert inv_repo.get_stock(prod_a.id) == Decimal("25.000")

    # 1. Purchase receipt: +50.000 packets
    inv_repo.record_movement(
        product_id=prod_a.id,
        movement_type=MovementType.PURCHASE_RECEIPT,
        quantity=Decimal("50.000"),
        unit_cost=Decimal("380.00"),
        reference_type="PURCHASE_ORDER",
        reference_id="PO-002",
    )
    assert inv_repo.get_stock(prod_a.id) == Decimal("75.000")

    # 2. Sale dispatch: -20.250 packets
    inv_repo.record_movement(
        product_id=prod_a.id,
        movement_type=MovementType.SALE_DISPATCH,
        quantity=Decimal("20.250"),
        reference_type="SALE",
        reference_id="INV-001",
    )
    assert inv_repo.get_stock(prod_a.id) == Decimal("54.750")

    # 3. Customer return inward: +2.000 packets
    inv_repo.record_movement(
        product_id=prod_a.id,
        movement_type=MovementType.RETURN_INWARD,
        quantity=Decimal("2.000"),
        reference_type="SALE_RETURN",
        reference_id="RET-001",
    )
    assert inv_repo.get_stock(prod_a.id) == Decimal("56.750")

    # 4. Supplier return outward: -5.000 packets
    inv_repo.record_movement(
        product_id=prod_a.id,
        movement_type=MovementType.RETURN_OUTWARD,
        quantity=Decimal("5.000"),
        reference_type="SUPPLIER_RETURN",
        reference_id="SRET-001",
    )
    assert inv_repo.get_stock(prod_a.id) == Decimal("51.750")

    # 5. Adjustment increase: +1.250 packets
    inv_repo.record_movement(
        product_id=prod_a.id,
        movement_type=MovementType.ADJUSTMENT_INCREASE,
        quantity=Decimal("1.250"),
        notes="Physical stock count audit reconciliation",
    )
    assert inv_repo.get_stock(prod_a.id) == Decimal("53.000")

    # 6. Adjustment decrease: -3.000 packets
    inv_repo.record_movement(
        product_id=prod_a.id,
        movement_type=MovementType.ADJUSTMENT_DECREASE,
        quantity=Decimal("3.000"),
        notes="Damaged packaging during monsoon",
    )
    assert inv_repo.get_stock(prod_a.id) == Decimal("50.000")

    # Verify ProductRepository reports the exact same reconciled stock
    assert prod_repo.get_reconciled_stock(prod_a.id) == Decimal("50.000")


def test_inventory_validation_rules(db_session: Session, tenants: dict):
    """Verify inventory quantity rules and constraints."""
    ctx_a = tenants["tenant_a"]["context"]
    prod_a = tenants["tenant_a"]["product"]

    inv_repo = InventoryRepository(db_session, ctx_a)

    # Negative or zero quantities rejected
    with pytest.raises(BadRequestError):
        inv_repo.record_movement(
            product_id=prod_a.id,
            movement_type=MovementType.PURCHASE_RECEIPT,
            quantity=Decimal("-5.000"),
        )

    with pytest.raises(BadRequestError):
        inv_repo.record_movement(
            product_id=prod_a.id,
            movement_type=MovementType.PURCHASE_RECEIPT,
            quantity=Decimal("0.000"),
        )

    # Missing product rejected
    with pytest.raises(NotFoundError):
        inv_repo.record_movement(
            product_id="non-existent-product-id",
            movement_type=MovementType.PURCHASE_RECEIPT,
            quantity=Decimal("10.000"),
        )


def test_decimal_precision_no_float_drift(db_session: Session, tenants: dict):
    """Verify fractional operations maintain exact Decimal precision without float drift."""
    ctx_a = tenants["tenant_a"]["context"]

    # Create loose grain product
    prod_repo = ProductRepository(db_session, ctx_a)
    loose_rice = prod_repo.create_product(
        name="Basmati Rice Loose",
        selling_price=Decimal("110.00"),
        unit="kg",
    )

    inv_repo = InventoryRepository(db_session, ctx_a)

    # Inward 100 kg
    inv_repo.record_movement(
        product_id=loose_rice.id,
        movement_type=MovementType.PURCHASE_RECEIPT,
        quantity=Decimal("100.000"),
    )

    # 3 sales of 0.333 kg each
    for _ in range(3):
        inv_repo.record_movement(
            product_id=loose_rice.id,
            movement_type=MovementType.SALE_DISPATCH,
            quantity=Decimal("0.333"),
        )

    # 100 - (3 * 0.333) = 100 - 0.999 = 99.001 kg
    stock = inv_repo.get_stock(loose_rice.id)
    assert stock == Decimal("99.001")
    assert isinstance(stock, Decimal)
