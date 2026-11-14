"""tenant scoped retrieval chunks and AI conversation history

Revision ID: 1b2c3d4e5f6a
Revises: 1a2b3c4d5e6f
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1b2c3d4e5f6a"
down_revision: str | Sequence[str] | None = "1a2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "business_id",
            sa.String(36),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("uploaded_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("embedding_version", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "document_id", "chunk_index", name="uq_knowledge_chunk"),
    )
    op.create_index(
        "ix_knowledge_tenant_document", "knowledge_chunks", ["business_id", "document_id"]
    )
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "business_id",
            sa.String(36),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_conversations_business_id", "ai_conversations", ["business_id"])
    op.create_index("ix_ai_conversations_created_at", "ai_conversations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_conversations_created_at", table_name="ai_conversations")
    op.drop_index("ix_ai_conversations_business_id", table_name="ai_conversations")
    op.drop_table("ai_conversations")
    op.drop_index("ix_knowledge_tenant_document", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
