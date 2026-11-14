"""Inventory models and movement tracking."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid, utc_now

if TYPE_CHECKING:
    from app.models.catalogue import Product
    from app.models.identity import Business


class MovementType(StrEnum):
    """Inventory movement classification defining direction."""

    PURCHASE_RECEIPT = "PURCHASE_RECEIPT"  # Inward (+)
    SALE_DISPATCH = "SALE_DISPATCH"  # Outward (-)
    ADJUSTMENT_INCREASE = "ADJUSTMENT_INCREASE"  # Inward (+)
    ADJUSTMENT_DECREASE = "ADJUSTMENT_DECREASE"  # Outward (-)
    RETURN_INWARD = "RETURN_INWARD"  # Inward (+) (customer return)
    RETURN_OUTWARD = "RETURN_OUTWARD"  # Outward (-) (return to supplier)


INWARD_MOVEMENTS = {
    MovementType.PURCHASE_RECEIPT,
    MovementType.ADJUSTMENT_INCREASE,
    MovementType.RETURN_INWARD,
    "PURCHASE_RECEIPT",
    "ADJUSTMENT_INCREASE",
    "RETURN_INWARD",
}


class InventoryMovement(Base):
    """Immutable audit record of all physical inventory changes.

    Invariant: Physical stock for a product is strictly reconciled to the sum
    of all its inventory movements. Stock is never mutated directly without a movement.
    """

    __tablename__ = "inventory_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3, asdecimal=True), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # e.g. "SALE", "PURCHASE_ORDER", "INITIAL_STOCK", "INVENTORY_AUDIT"
    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    business: Mapped["Business"] = relationship("Business", back_populates="inventory_movements")
    product: Mapped["Product"] = relationship("Product", back_populates="inventory_movements")

    @property
    def is_inward(self) -> bool:
        """Return True if movement increases on-hand stock."""
        return self.movement_type in INWARD_MOVEMENTS

    @property
    def signed_quantity(self) -> Decimal:
        """Return positive Decimal for inward movements, negative for outward movements."""
        qty = abs(self.quantity)
        return qty if self.is_inward else -qty

    __table_args__ = (
        Index("ix_inv_movements_business_product", "business_id", "product_id"),
        Index("ix_inv_movements_business_created", "business_id", "created_at"),
    )


class ForecastRun(Base):
    """Persist forecast result and method metadata for reproducibility."""

    __tablename__ = "inventory_forecast_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    forecast_method: Mapped[str] = mapped_column(String(40), nullable=False)
    training_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    __table_args__ = (
        Index("ix_forecast_run_business_product_time", "business_id", "product_id", "created_at"),
    )
