"""Typed schemas for AI Data Centre, file upload, candidate extraction, and review."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CandidateSaleItem(BaseModel):
    """Candidate line item extracted from invoice or CSV."""

    model_config = ConfigDict(extra="ignore")

    product_name: str
    sku: str | None = None
    quantity: Decimal = Field(..., gt=Decimal("0.000"))
    unit_price: Decimal = Field(..., ge=Decimal("0.00"))
    unit_cost: Decimal | None = None
    total_amount: Decimal = Field(..., ge=Decimal("0.00"))
    source_row: int | None = None


class CandidateSale(BaseModel):
    """Candidate sales transaction awaiting owner review."""

    model_config = ConfigDict(extra="ignore")

    sale_number: str | None = None
    sold_at: datetime | None = None
    total_amount: Decimal = Field(..., gt=Decimal("0.00"))
    payment_mode: str = Field(default="CASH")
    customer_name: str | None = None
    items: list[CandidateSaleItem] = Field(default_factory=list)
    source_row: int | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class CandidateExpense(BaseModel):
    """Candidate expense bill extracted from receipt or CSV."""

    model_config = ConfigDict(extra="ignore")

    category: str = Field(default="OTHER")
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    expense_date: datetime | None = None
    description: str | None = None
    payment_mode: str = Field(default="CASH")
    source_row: int | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class CandidateCreditTransaction(BaseModel):
    """Candidate Udhar credit entry or repayment.

    Invariant: Udhar extraction produces drafts only. Ambiguous customer matches or
    transaction directions must be flagged with ambiguity_flags for owner resolution.
    """

    model_config = ConfigDict(extra="ignore")

    customer_candidate_name: str
    phone: str | None = None
    transaction_type: str = Field(
        ..., description="'CHARGE' (credit given) or 'REPAYMENT' (cash/UPI collected)"
    )
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    transaction_at: datetime | None = None
    due_at: datetime | None = None
    description: str | None = None
    reference: str | None = None
    source_page: int | None = None
    source_row: int | None = None
    snippet: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    ambiguity_flags: list[str] = Field(default_factory=list)
    requires_owner_review: bool = Field(default=True)


class DocumentExtractionData(BaseModel):
    """Aggregated candidates extracted from a document."""

    extraction_type: str  # "SALES", "EXPENSES", "INVENTORY", "UDHAR_LEDGER", "MIXED"
    sales: list[CandidateSale] = Field(default_factory=list)
    expenses: list[CandidateExpense] = Field(default_factory=list)
    credit_transactions: list[CandidateCreditTransaction] = Field(default_factory=list)
    invalid_rows: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Records that failed validation with reasons; never silently dropped",
    )


class UploadDocumentResponse(BaseModel):
    """Response after file upload and fingerprinting."""

    document_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    sha256_hash: str
    status: str
    message: str


class DocumentExtractionResponse(BaseModel):
    """Full extraction status and candidate records for owner review screen."""

    document_id: str
    filename: str
    file_type: str
    sha256_hash: str
    status: str
    extraction_type: str
    extraction_version: str
    data: DocumentExtractionData
    ambiguity_count: int
    is_confirmed: bool
    confirmed_at: datetime | None = None


class DocumentConfirmRequest(BaseModel):
    """Owner review confirmation payload with any edits."""

    confirmed_sales: list[CandidateSale] | None = None
    confirmed_expenses: list[CandidateExpense] | None = None
    confirmed_credit_transactions: list[CandidateCreditTransaction] | None = None


class DocumentConfirmResponse(BaseModel):
    """Result of transactional ledger posting."""

    document_id: str
    is_confirmed: bool
    sales_posted: int
    expenses_posted: int
    credit_transactions_posted: int
    message: str


class NaturalLanguageIngestionRequest(BaseModel):
    """Raw text or conversational message ingestion request."""

    text: str = Field(..., min_length=2, max_length=2000)
    default_date: datetime | None = None


class ImportPreviewResponse(BaseModel):
    """Preview of parsed tabular data (CSV/XLSX) before confirmation."""

    filename: str
    file_type: str
    detected_type: str  # "SALES", "EXPENSES", "UDHAR_LEDGER"
    total_rows: int
    valid_rows_count: int
    invalid_rows_count: int
    candidates: DocumentExtractionData


class UploadedDocumentSummary(BaseModel):
    """Summary of an uploaded document for list and status displays."""

    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    sha256_hash: str
    status: str
    ambiguity_count: int = 0
    is_confirmed: bool = False
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated list of uploaded documents."""

    documents: list[UploadedDocumentSummary]
    total: int
