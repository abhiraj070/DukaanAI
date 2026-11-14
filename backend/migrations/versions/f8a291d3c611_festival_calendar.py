"""Tenant editable festival calendar."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a291d3c611"
down_revision: str | Sequence[str] | None = "c5b1a34ed206"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "festival_calendar_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "business_id", "name", "start_date", name="uq_festival_business_name_start"
        ),
    )
    op.create_index(
        "ix_festival_business_dates",
        "festival_calendar_events",
        ["business_id", "start_date", "end_date"],
    )


def downgrade() -> None:
    op.drop_table("festival_calendar_events")
