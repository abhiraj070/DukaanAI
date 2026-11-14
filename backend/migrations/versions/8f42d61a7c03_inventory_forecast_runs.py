"""Persist inventory forecast runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f42d61a7c03"
down_revision: str | Sequence[str] | None = "2cab4187687c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_forecast_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("forecast_method", sa.String(40), nullable=False),
        sa.Column("training_window_days", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_forecast_run_business_product_time",
        "inventory_forecast_runs",
        ["business_id", "product_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("inventory_forecast_runs")
