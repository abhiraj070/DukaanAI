"""Typed schemas for Udhar Management, Customer Ledger, Aging, and Statements."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AgingBucket(BaseModel):
    """Aging distribution bucket for overdue receivables."""

    model_config = ConfigDict(frozen=True)

    bucket_key: str  # "NOT_DUE", "1_7_DAYS", "8_30_DAYS", "31_60_DAYS", "60_PLUS_DAYS"
    label: str  # "Current (Not Due)", "1–7 Days Overdue", etc.
    amount: Decimal
    customer_count: int


class UdharSummary(BaseModel):
    """Store-wide customer credit (udhar) summary metrics.

    Principles:
    - Receivables are not cash.
    - Derived strictly from confirmed ledger entries and allocations.
    """

    model_config = ConfigDict(frozen=True)

    total_receivables: Decimal = Field(
        ..., description="Total outstanding customer debt owed to the business"
    )
    overdue_amount: Decimal = Field(..., description="Total amount with past due_date")
    customers_with_balance_count: int
    aging_buckets: list[AgingBucket]
    currency: str = "INR"


class StatementLineItem(BaseModel):
    """Line item on an auditable customer credit statement."""

    model_config = ConfigDict(frozen=True)

    transaction_id: str
    transaction_at: datetime
    transaction_type: str
    description: str | None = None
    reference: str | None = None
    charge_amount: Decimal | None = None
    repayment_amount: Decimal | None = None
    running_balance: Decimal


class CustomerStatement(BaseModel):
    """Reconciled customer ledger statement."""

    model_config = ConfigDict(frozen=True)

    customer_id: str
    customer_name: str
    phone: str | None = None
    currency: str = "INR"
    start_date: datetime | None = None
    end_date: datetime | None = None
    opening_balance: Decimal
    total_charges: Decimal
    total_repayments: Decimal
    closing_balance: Decimal
    lines: list[StatementLineItem]
