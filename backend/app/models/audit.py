"""Audit logging foundation for tracking operational and financial actions."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid, utc_now

if TYPE_CHECKING:
    from app.models.identity import Business


class AuditLog(Base):
    """Audit log record for business operations and ledger events."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # "CREATE", "UPDATE", "DELETE", "CONFIRM", "REVERSE", "ALLOCATE", "LOGIN"
    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # "PRODUCT", "CUSTOMER", "CREDIT_TRANSACTION", "INVENTORY_MOVEMENT", "SALE"
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    changes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    business: Mapped["Business"] = relationship("Business", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_business_entity", "business_id", "entity_type", "entity_id"),
        Index("ix_audit_logs_business_created", "business_id", "created_at"),
    )
