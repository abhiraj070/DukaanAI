from decimal import Decimal

import pytest

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.domain.purchase_orders.service import PurchaseOrderService
from app.models.inventory import InventoryMovement
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderItemInput,
    PurchaseOrderReceipt,
    ReceiptLine,
)


def test_po_approval_does_not_change_stock_and_receipt_is_idempotent(db_session, tenants):
    ctx = tenants["tenant_a"]["context"]
    product = tenants["tenant_a"]["product"]
    service = PurchaseOrderService(db_session, ctx)
    po = service.create(
        PurchaseOrderCreate(
            idempotency_key="create-1",
            items=[
                PurchaseOrderItemInput(
                    product_id=product.id,
                    quantity=Decimal("4"),
                    unit_cost=Decimal("12.50"),
                    unit_cost_source="supplier quote",
                )
            ],
        )
    )
    assert po.status == "DRAFT" and po.total_amount == Decimal("50.00")
    service.transition(po.id, "approve")
    assert db_session.query(InventoryMovement).filter_by(reference_id=po.id).count() == 0
    request = PurchaseOrderReceipt(
        idempotency_key="receipt-1",
        items=[ReceiptLine(item_id=po.items[0].id, quantity=Decimal("2"))],
    )
    partial = service.receive(po.id, request)
    service.receive(po.id, request)
    assert partial.status == "PARTIALLY_RECEIVED"
    assert db_session.query(InventoryMovement).filter_by(reference_id=po.id).count() == 1


def test_po_cannot_be_received_before_approval_or_over_received(db_session, tenants):
    ctx = tenants["tenant_a"]["context"]
    product = tenants["tenant_a"]["product"]
    service = PurchaseOrderService(db_session, ctx)
    po = service.create(
        PurchaseOrderCreate(
            idempotency_key="create-2",
            items=[
                PurchaseOrderItemInput(
                    product_id=product.id,
                    quantity=Decimal("1"),
                    unit_cost=Decimal("1"),
                    unit_cost_source="catalogue",
                )
            ],
        )
    )
    with pytest.raises(ConflictError):
        service.receive(
            po.id,
            PurchaseOrderReceipt(
                idempotency_key="r",
                items=[ReceiptLine(item_id=po.items[0].id, quantity=Decimal("1"))],
            ),
        )
    service.transition(po.id, "approve")
    with pytest.raises(BadRequestError):
        service.receive(
            po.id,
            PurchaseOrderReceipt(
                idempotency_key="r2",
                items=[ReceiptLine(item_id=po.items[0].id, quantity=Decimal("2"))],
            ),
        )


def test_po_tenant_isolation(db_session, tenants):
    ctx_b = tenants["tenant_b"]["context"]
    product_a = tenants["tenant_a"]["product"]
    service = PurchaseOrderService(db_session, ctx_b)
    with pytest.raises(NotFoundError):
        service.create(
            PurchaseOrderCreate(
                idempotency_key="foreign-product",
                items=[
                    PurchaseOrderItemInput(
                        product_id=product_a.id,
                        quantity=Decimal("1"),
                        unit_cost=Decimal("1"),
                        unit_cost_source="manual",
                    )
                ],
            )
        )
