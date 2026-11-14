"""Owner-controlled purchase order draft and receipt endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.context import BusinessContext, get_business_context
from app.db.session import get_db
from app.domain.purchase_orders.service import PurchaseOrderService
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderReceipt,
    PurchaseOrderResponse,
)

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.get("", response_model=list[PurchaseOrderResponse])
def list_purchase_orders(
    context: BusinessContext = Depends(get_business_context), db: Session = Depends(get_db)
):
    return PurchaseOrderService(db, context).list()


@router.post("/drafts", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return PurchaseOrderService(db, context).create(payload)


@router.post("/{po_id}/approve", response_model=PurchaseOrderResponse)
def approve_purchase_order(
    po_id: str,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return PurchaseOrderService(db, context).transition(po_id, "approve")


@router.put("/{po_id}", response_model=PurchaseOrderResponse)
def update_purchase_order(
    po_id: str,
    payload: PurchaseOrderCreate,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return PurchaseOrderService(db, context).update_draft(po_id, payload)


@router.post("/{po_id}/cancel", response_model=PurchaseOrderResponse)
def cancel_purchase_order(
    po_id: str,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return PurchaseOrderService(db, context).transition(po_id, "cancel")


@router.post("/{po_id}/receive", response_model=PurchaseOrderResponse)
def receive_purchase_order(
    po_id: str,
    payload: PurchaseOrderReceipt,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return PurchaseOrderService(db, context).receive(po_id, payload)
