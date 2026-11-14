"""Tenant-safe purchase order lifecycle and receipt posting."""

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.core.context import BusinessContext
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.audit import AuditLog
from app.models.catalogue import Product, Supplier
from app.models.inventory import InventoryMovement, MovementType
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderReceipt,
    PurchaseOrderResponse,
)


class PurchaseOrderService:
    def __init__(self, db: Session, context: BusinessContext):
        self.db, self.context = db, context

    def _get(self, po_id: str) -> PurchaseOrder:
        po = (
            self.db.query(PurchaseOrder)
            .options(joinedload(PurchaseOrder.items))
            .filter_by(id=po_id, business_id=self.context.business_id)
            .first()
        )
        if po is None:
            raise NotFoundError("Purchase order not found")
        return po

    def _audit(self, action: str, po: PurchaseOrder, details: dict | None = None) -> None:
        self.db.add(
            AuditLog(
                business_id=self.context.business_id,
                user_id=self.context.user_id,
                action=action,
                entity_type="PURCHASE_ORDER",
                entity_id=po.id,
                changes_json=json.dumps(details or {}, sort_keys=True),
            )
        )

    def _response(self, po: PurchaseOrder) -> PurchaseOrderResponse:
        return PurchaseOrderResponse(
            id=po.id,
            supplier_id=po.supplier_id,
            status=po.status,
            notes=po.notes,
            total_amount=sum((i.quantity * i.unit_cost for i in po.items), Decimal("0.00")),
            items=po.items,
            created_at=po.created_at,
            approved_at=po.approved_at,
            received_at=po.received_at,
            cancelled_at=po.cancelled_at,
        )

    def list(self) -> list[PurchaseOrderResponse]:
        rows = (
            self.db.query(PurchaseOrder)
            .options(joinedload(PurchaseOrder.items))
            .filter_by(business_id=self.context.business_id)
            .order_by(PurchaseOrder.created_at.desc())
            .limit(200)
            .all()
        )
        return [self._response(row) for row in rows]

    def create(self, payload: PurchaseOrderCreate) -> PurchaseOrderResponse:
        existing = (
            self.db.query(PurchaseOrder)
            .options(joinedload(PurchaseOrder.items))
            .filter_by(
                business_id=self.context.business_id, idempotency_key=payload.idempotency_key
            )
            .first()
        )
        if existing:
            return self._response(existing)
        if (
            payload.supplier_id
            and not self.db.query(Supplier.id)
            .filter_by(id=payload.supplier_id, business_id=self.context.business_id)
            .first()
        ):
            raise NotFoundError("Supplier not found")
        po = PurchaseOrder(
            business_id=self.context.business_id,
            supplier_id=payload.supplier_id,
            notes=payload.notes,
            idempotency_key=payload.idempotency_key,
            created_by=self.context.user_id,
        )
        for line in payload.items:
            product = (
                self.db.query(Product)
                .filter_by(id=line.product_id, business_id=self.context.business_id, is_active=True)
                .first()
            )
            if not product:
                raise NotFoundError(f"Product {line.product_id} not found")
            po.items.append(
                PurchaseOrderItem(
                    business_id=self.context.business_id,
                    product_id=product.id,
                    product_name=product.name,
                    quantity=line.quantity,
                    unit_cost=line.unit_cost,
                    unit_cost_source=line.unit_cost_source,
                )
            )
        self.db.add(po)
        self.db.flush()
        self._audit("CREATE", po, {"status": "DRAFT", "items": len(po.items)})
        return self._response(po)

    def transition(self, po_id: str, action: str) -> PurchaseOrderResponse:
        po = self._get(po_id)
        if action == "approve" and po.status == "DRAFT":
            po.status, po.approved_at, po.approved_by = (
                "APPROVED",
                datetime.now(UTC),
                self.context.user_id,
            )
        elif action == "cancel" and po.status in {"DRAFT", "APPROVED"}:
            po.status, po.cancelled_at = "CANCELLED", datetime.now(UTC)
        else:
            raise ConflictError(f"Cannot {action} a purchase order in {po.status} status")
        self._audit(action.upper(), po)
        self.db.flush()
        return self._response(po)

    def receive(self, po_id: str, payload: PurchaseOrderReceipt) -> PurchaseOrderResponse:
        po = self._get(po_id)
        if po.status not in {"APPROVED", "PARTIALLY_RECEIVED"}:
            raise ConflictError(f"Cannot receive a purchase order in {po.status} status")
        key = f"po-receipt:{po.id}:{payload.idempotency_key}"
        duplicate = (
            self.db.query(InventoryMovement.id)
            .filter_by(business_id=self.context.business_id, reference_type="PO_RECEIPT", notes=key)
            .first()
        )
        if duplicate:
            return self._response(po)
        by_id = {item.id: item for item in po.items}
        lines = []
        for line in payload.items:
            item = by_id.get(line.item_id)
            if not item or line.quantity > item.quantity - item.received_quantity:
                raise BadRequestError(
                    "Receipt quantity exceeds the remaining purchase order quantity"
                )
            lines.append((item, line.quantity))
        if not lines:
            raise BadRequestError("Receipt must include at least one valid line")
        for item, quantity in lines:
            item.received_quantity += quantity
            self.db.add(
                InventoryMovement(
                    business_id=self.context.business_id,
                    product_id=item.product_id,
                    movement_type=MovementType.PURCHASE_RECEIPT.value,
                    quantity=quantity,
                    unit_cost=item.unit_cost,
                    reference_type="PO_RECEIPT",
                    reference_id=po.id,
                    notes=key,
                    created_by=self.context.user_id,
                )
            )
        po.status = (
            "RECEIVED"
            if all(i.received_quantity == i.quantity for i in po.items)
            else "PARTIALLY_RECEIVED"
        )
        if po.status == "RECEIVED":
            po.received_at = datetime.now(UTC)
        self._audit(
            "RECEIVE", po, {"idempotency_key": payload.idempotency_key, "lines": len(lines)}
        )
        self.db.flush()
        return self._response(po)
