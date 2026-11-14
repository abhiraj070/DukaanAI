"""Document ingestion models: UploadedDocument and DocumentExtraction."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_uuid, utc_now

if TYPE_CHECKING:
    from app.models.identity import Business


class UploadedDocument(Base):
    """Uploaded physical document (PDF, CSV, XLSX, Image, or Raw Text)."""

    __tablename__ = "uploaded_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "CSV", "XLSX", "PDF", "IMAGE", "TEXT"
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", nullable=False
    )  # "PENDING", "PROCESSING", "PROCESSED", "CONFIRMED", "FAILED"
    uploaded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    business: Mapped["Business"] = relationship("Business")
    extractions: Mapped[list["DocumentExtraction"]] = relationship(
        "DocumentExtraction", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_uploaded_docs_business_sha256", "business_id", "sha256_hash"),
        Index("ix_uploaded_docs_business_status", "business_id", "status"),
    )


class DocumentExtraction(Base):
    """Candidate structured records extracted from an uploaded document awaiting owner confirmation.

    Invariant: Extracted records are drafts only. Consequential transactions are posted
    strictly when reviewed and confirmed by the business owner.
    """

    __tablename__ = "document_extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("uploaded_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    extraction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "SALES", "EXPENSES", "INVENTORY", "UDHAR_LEDGER", "MIXED"
    extraction_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)
    raw_extracted_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_candidates_json: Mapped[str] = mapped_column(Text, nullable=False)
    ambiguity_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    document: Mapped["UploadedDocument"] = relationship(
        "UploadedDocument", back_populates="extractions"
    )

    __table_args__ = (
        Index("ix_doc_extractions_business_confirmed", "business_id", "is_confirmed"),
    )
