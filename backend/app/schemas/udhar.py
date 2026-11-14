"""Typed schemas for Udhar Management, Customer Ledger, Aging, Statements, and Reminders."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

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


# Customer Management Schemas


class CustomerDuplicateMatch(BaseModel):
    """Potential duplicate customer identified during creation or lookup."""

    model_config = ConfigDict(frozen=True)

    existing_customer_id: str
    existing_display_name: str
    existing_phone: str | None = None
    match_type: str  # "PHONE_MATCH", "EXACT_NAME", "FUZZY_NAME"


class CustomerCreate(BaseModel):
    """Payload to create a new customer with optional opening balance and credit limit."""

    display_name: str = Field(..., min_length=1, max_length=255)
    phone_e164: str | None = Field(None, max_length=50)
    notes: str | None = None
    credit_limit: Decimal | None = Field(None, ge=Decimal("0.00"))
    opening_balance: Decimal | None = Field(None, ge=Decimal("0.00"))
    opening_balance_due_at: datetime | None = None
    opening_balance_notes: str | None = None


class CustomerUpdate(BaseModel):
    """Payload to update customer metadata and credit limits."""

    display_name: str | None = Field(None, min_length=1, max_length=255)
    phone_e164: str | None = Field(None, max_length=50)
    notes: str | None = None
    credit_limit: Decimal | None = Field(None, ge=Decimal("0.00"))
    reminder_consent_status: str | None = None  # "NOT_REQUESTED", "CONSENTED", "OPTED_OUT"


class CustomerResponse(BaseModel):
    """Authoritative customer profile with derived udhar balances and aging status."""

    model_config = ConfigDict(frozen=True)

    id: str
    display_name: str
    phone_e164: str | None = None
    notes: str | None = None
    credit_limit: Decimal | None = None
    currency: str = "INR"
    is_active: bool = True
    reminder_consent_status: str = "NOT_REQUESTED"
    created_at: datetime
    archived_at: datetime | None = None
    outstanding_balance: Decimal = Decimal("0.00")
    overdue_amount: Decimal = Decimal("0.00")
    aging_bucket: str = "NOT_DUE"
    transaction_count: int = 0


class CustomerCreateResponse(BaseModel):
    """Response returned upon customer creation, including any duplicate warnings."""

    model_config = ConfigDict(frozen=True)

    customer: CustomerResponse
    warnings: list[str] = []
    duplicate_matches: list[CustomerDuplicateMatch] = []


# Credit Transactions & Allocations


class ChargeCreate(BaseModel):
    """Payload to record a new credit sale (charge) on a customer's account."""

    customer_id: str
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Positive charge amount")
    due_at: datetime | None = None
    description: str | None = None
    reference: str | None = None
    idempotency_key: str | None = None


class ChargeResponse(BaseModel):
    """Authoritative response after recording a credit charge."""

    model_config = ConfigDict(frozen=True)

    transaction_id: str
    customer_id: str
    amount: Decimal
    transaction_type: str
    transaction_at: datetime
    due_at: datetime | None = None
    description: str | None = None
    reference: str | None = None
    status: str
    credit_limit_warning: str | None = None
    new_balance: Decimal


class AllocationInput(BaseModel):
    """Repayment allocation against a specific open charge transaction."""

    charge_transaction_id: str
    amount: Decimal = Field(..., gt=Decimal("0.00"))


class AllocationResponse(BaseModel):
    """Allocated payment slice."""

    model_config = ConfigDict(frozen=True)

    id: str
    charge_transaction_id: str
    allocated_amount: Decimal
    created_at: datetime


class RepaymentCreate(BaseModel):
    """Payload to record a customer repayment with optional multi-charge allocations."""

    customer_id: str
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Positive repayment collection")
    payment_mode: Literal["CASH", "UPI", "BANK_TRANSFER", "CHEQUE", "OTHER"] = "CASH"
    reference: str | None = None
    description: str | None = None
    idempotency_key: str | None = None
    allocations: list[AllocationInput] | None = None
    auto_allocate: bool = True


class RepaymentResponse(BaseModel):
    """Authoritative response after recording a customer repayment."""

    model_config = ConfigDict(frozen=True)

    transaction_id: str
    customer_id: str
    amount: Decimal
    payment_mode: str
    transaction_at: datetime
    reference: str | None = None
    status: str
    allocated_amount: Decimal
    unallocated_amount: Decimal
    allocations: list[AllocationResponse]
    new_balance: Decimal


class ReversalCreate(BaseModel):
    """Payload to reverse an existing credit transaction."""

    reason: str = Field(..., min_length=3, description="Audit reason for reversing transaction")


class ReversalResponse(BaseModel):
    """Authoritative response after compensating reversal posting."""

    model_config = ConfigDict(frozen=True)

    reversal_transaction_id: str
    original_transaction_id: str
    amount: Decimal
    reversed_at: datetime
    new_balance: Decimal


class CustomerLedgerResponse(BaseModel):
    """Complete chronological ledger for a specific customer."""

    model_config = ConfigDict(frozen=True)

    customer_id: str
    customer_name: str
    outstanding_balance: Decimal
    credit_limit: Decimal | None = None
    currency: str = "INR"
    lines: list[StatementLineItem]


# Reminder Draft Schemas


class ReminderDraftRequest(BaseModel):
    """Request to generate an un-sent reminder preview."""

    language: Literal["Hinglish", "Hindi", "English"] = "Hinglish"


class ReminderDraftResponse(BaseModel):
    """Un-sent reminder preview with WhatsApp link and consent status."""

    model_config = ConfigDict(frozen=True)

    customer_id: str
    customer_name: str
    phone: str | None = None
    outstanding_balance: Decimal
    overdue_amount: Decimal
    due_at: datetime | None = None
    language: str
    draft_text: str
    whatsapp_link: str | None = None
    consent_status: str
    disclaimer: str
