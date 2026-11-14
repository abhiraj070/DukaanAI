"""Purchase order workflow API contracts."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PurchaseOrderItemInput(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    unit_cost_source: str = Field(min_length=1, max_length=80)


class PurchaseOrderCreate(BaseModel):
    supplier_id: str | None = None
    notes: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)
    items: list[PurchaseOrderItemInput] = Field(min_length=1)


class PurchaseOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    product_name: str
    quantity: Decimal
    unit_cost: Decimal
    unit_cost_source: str
    received_quantity: Decimal


class PurchaseOrderResponse(BaseModel):
    id: str
    supplier_id: str | None
    status: str
    notes: str | None
    total_amount: Decimal
    items: list[PurchaseOrderItemResponse]
    created_at: datetime
    approved_at: datetime | None
    received_at: datetime | None
    cancelled_at: datetime | None


class ReceiptLine(BaseModel):
    item_id: str
    quantity: Decimal = Field(gt=0)


class PurchaseOrderReceipt(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    items: list[ReceiptLine] = Field(min_length=1)
