"""Udhar (Customer Credit) models: Customer, CreditAccount, CreditTransaction, CreditAllocation."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
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
    from app.models.operations import Sale


class TransactionType(StrEnum):
    """Udhar ledger transaction types defining financial direction."""

    CHARGE = "CHARGE"  # Increases receivable balance (+)
    REPAYMENT = "REPAYMENT"  # Reduces receivable balance via collection (-)
    ADJUSTMENT_DEBIT = "ADJUSTMENT_DEBIT"  # Authorized correction increasing receivable (+)
    ADJUSTMENT_CREDIT = "ADJUSTMENT_CREDIT"  # Authorized correction decreasing receivable (-)
    REVERSAL = "REVERSAL"  # Compensating transaction referencing original entry


class TransactionStatus(StrEnum):
    """Lifecycle state of a ledger transaction."""

    DRAFT = "DRAFT"  # Extracted / pending owner review
    CONFIRMED = "CONFIRMED"  # Postable and active on ledger
    REVERSED = "REVERSED"  # Counteracted by a REVERSAL transaction


class Customer(Base):
    """Customer entity with optional credit relationship."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone_e164: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_consent_status: Mapped[str] = mapped_column(
        String(50), default="NOT_REQUESTED", nullable=False
    )  # "NOT_REQUESTED", "CONSENTED", "OPTED_OUT"
    reminder_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="customers")
    credit_account: Mapped[Optional["CreditAccount"]] = relationship(
        "CreditAccount", back_populates="customer", uselist=False, cascade="all, delete-orphan"
    )
    sales: Mapped[list["Sale"]] = relationship("Sale", back_populates="customer")

    __table_args__ = (
        Index("ix_customers_business_name", "business_id", "display_name"),
        Index("ix_customers_business_phone", "business_id", "phone_e164"),
    )


class CreditAccount(Base):
    """Credit account linked 1:1 to a customer within a business."""

    __tablename__ = "credit_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    credit_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2, asdecimal=True), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="credit_account")
    transactions: Mapped[list["CreditTransaction"]] = relationship(
        "CreditTransaction", back_populates="credit_account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("business_id", "customer_id", name="uq_credit_accounts_business_customer"),
    )


class CreditTransaction(Base):
    """Append-only financial transaction on the Udhar credit ledger.

    Invariant: Confirmed transactions are never destructively edited or deleted.
    Outstanding balances are derived from confirmed charges and allocations.
    """

    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    credit_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credit_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "CHARGE", "REPAYMENT", "ADJUSTMENT_DEBIT", "ADJUSTMENT_CREDIT", "REVERSAL"
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2, asdecimal=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    transaction_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="CONFIRMED", nullable=False
    )  # "DRAFT", "CONFIRMED", "REVERSED"
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reverses_transaction_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("credit_transactions.id", ondelete="SET NULL"), nullable=True
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    credit_account: Mapped["CreditAccount"] = relationship(
        "CreditAccount", back_populates="transactions"
    )
    reverses_transaction: Mapped[Optional["CreditTransaction"]] = relationship(
        "CreditTransaction",
        remote_side="CreditTransaction.id",
        back_populates="reversed_by",
    )
    reversed_by: Mapped[list["CreditTransaction"]] = relationship(
        "CreditTransaction",
        back_populates="reverses_transaction",
    )
    allocations_as_repayment: Mapped[list["CreditAllocation"]] = relationship(
        "CreditAllocation",
        foreign_keys="CreditAllocation.repayment_transaction_id",
        back_populates="repayment_transaction",
        cascade="all, delete-orphan",
    )
    allocations_as_charge: Mapped[list["CreditAllocation"]] = relationship(
        "CreditAllocation",
        foreign_keys="CreditAllocation.charge_transaction_id",
        back_populates="charge_transaction",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_credit_trans_account_date", "credit_account_id", "transaction_at"),
        Index("ix_credit_trans_business_status", "business_id", "status"),
        Index("ix_credit_trans_idempotency", "business_id", "idempotency_key"),
    )


class CreditAllocation(Base):
    """Allocation of a repayment transaction against an outstanding charge transaction.

    Invariant: Repayments reduce customer receivables through explicit allocations.
    Total allocated amount cannot exceed the repayment amount or open charge balance.
    """

    __tablename__ = "credit_allocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repayment_transaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credit_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    charge_transaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("credit_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2, asdecimal=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    repayment_transaction: Mapped["CreditTransaction"] = relationship(
        "CreditTransaction",
        foreign_keys=[repayment_transaction_id],
        back_populates="allocations_as_repayment",
    )
    charge_transaction: Mapped["CreditTransaction"] = relationship(
        "CreditTransaction",
        foreign_keys=[charge_transaction_id],
        back_populates="allocations_as_charge",
    )

    __table_args__ = (
        Index("ix_credit_alloc_repayment", "repayment_transaction_id"),
        Index("ix_credit_alloc_charge", "charge_transaction_id"),
    )
