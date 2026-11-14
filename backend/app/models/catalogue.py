"""Catalogue models: Category, Supplier, Product, and SupplierProduct."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid, utc_now

if TYPE_CHECKING:
    from app.models.identity import Business
    from app.models.inventory import InventoryMovement
    from app.models.operations import SaleItem


class Category(Base):
    """Product category within a business."""

    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    business: Mapped["Business"] = relationship("Business", back_populates="categories")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="category")

    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_categories_business_name"),)


class Supplier(Base):
    """Supplier / distributor entity."""

    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    business: Mapped["Business"] = relationship("Business", back_populates="suppliers")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="supplier")
    supplier_products: Mapped[list["SupplierProduct"]] = relationship(
        "SupplierProduct", back_populates="supplier", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_suppliers_business_name"),)


class Product(Base):
    """Product SKU entity."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supplier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(String(50), default="pc", nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=False)
    cost_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2, asdecimal=True), nullable=True
    )
    min_stock_level: Mapped[Decimal] = mapped_column(
        Numeric(12, 3, asdecimal=True), default=Decimal("0.000"), nullable=False
    )
    reorder_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3, asdecimal=True), default=Decimal("0.000"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    business: Mapped["Business"] = relationship("Business", back_populates="products")
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="products")
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier", back_populates="products")
    inventory_movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement", back_populates="product", cascade="all, delete-orphan"
    )
    sale_items: Mapped[list["SaleItem"]] = relationship("SaleItem", back_populates="product")
    supplier_links: Mapped[list["SupplierProduct"]] = relationship(
        "SupplierProduct", back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_products_business_name", "business_id", "name"),
        Index("ix_products_business_sku", "business_id", "sku"),
    )


class SupplierProduct(Base):
    """Supplier-product procurement relationship with lead times, MOQ, and pack sizes."""

    __tablename__ = "supplier_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2, asdecimal=True), nullable=False)
    moq: Mapped[Decimal] = mapped_column(
        Numeric(12, 3, asdecimal=True), default=Decimal("1.000"), nullable=False
    )
    pack_size: Mapped[Decimal] = mapped_column(
        Numeric(12, 3, asdecimal=True), default=Decimal("1.000"), nullable=False
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="supplier_products")
    product: Mapped["Product"] = relationship("Product", back_populates="supplier_links")

    __table_args__ = (
        UniqueConstraint("supplier_id", "product_id", name="uq_supplier_products_supplier_product"),
    )
