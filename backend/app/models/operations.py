"""Operations models: Sale, SaleItem, and Expense."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid, utc_now

if TYPE_CHECKING:
    from app.models.catalogue import Product
    from app.models.identity import Business
    from app.models.udhar import Customer


class Sale(Base):
    """Customer sale / bill transaction."""

    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sale_number: Mapped[str] = mapped_column(String(100), nullable=False)
    sold_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=False)
    payment_mode: Mapped[str] = mapped_column(
        String(50), default="CASH", nullable=False
    )  # "CASH", "UPI", "CREDIT", "SPLIT"
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="COMPLETED", nullable=False
    )  # "COMPLETED", "VOIDED", "RETURNED"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    business: Mapped["Business"] = relationship("Business", back_populates="sales")
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="sales")
    items: Mapped[list["SaleItem"]] = relationship(
        "SaleItem", back_populates="sale", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("business_id", "sale_number", name="uq_sales_business_sale_number"),
        Index("ix_sales_business_sold_at", "business_id", "sold_at"),
    )


class SaleItem(Base):
    """Line item on a sale."""

    __tablename__ = "sale_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sale_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3, asdecimal=True), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=False)

    sale: Mapped["Sale"] = relationship("Sale", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="sale_items")


class Expense(Base):
    """Store operating expense."""

    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # "RENT", "UTILITIES", "SALARY", "TRANSPORT", "MAINTENANCE", "OTHER"
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=False)
    expense_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_mode: Mapped[str] = mapped_column(String(50), default="CASH", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    business: Mapped["Business"] = relationship("Business", back_populates="expenses")

    __table_args__ = (Index("ix_expenses_business_date", "business_id", "expense_date"),)
