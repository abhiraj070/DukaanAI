"""Add tenant-scoped purchase order workflow."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1a2b3c4d5e6f"
down_revision: str | Sequence[str] | None = "f8a291d3c611"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), nullable=False),
        sa.Column("supplier_id", sa.String(36)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("approved_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_po_business_idempotency"),
    )
    op.create_index("ix_purchase_orders_business_id", "purchase_orders", ["business_id"])
    op.create_index("ix_po_business_status", "purchase_orders", ["business_id", "status"])
    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_cost_source", sa.String(80), nullable=False),
        sa.Column("received_quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_purchase_order_items_business_id", "purchase_order_items", ["business_id"])
    op.create_index(
        "ix_purchase_order_items_purchase_order_id", "purchase_order_items", ["purchase_order_id"]
    )


def downgrade() -> None:
    op.drop_table("purchase_order_items")
    op.drop_table("purchase_orders")
