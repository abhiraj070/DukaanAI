"""Persist tenant-scoped what-if scenarios."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5b1a34ed206"
down_revision: str | Sequence[str] | None = "8f42d61a7c03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), nullable=False),
        sa.Column("scenario_name", sa.String(160), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_scenario_business_created", "scenario_runs", ["business_id", "created_at"])


def downgrade() -> None:
    op.drop_table("scenario_runs")
