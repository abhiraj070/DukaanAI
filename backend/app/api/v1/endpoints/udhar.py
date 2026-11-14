"""API endpoints for Udhar (Customer Credit) Management, Ledger, Statements, and Reminders."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.context import BusinessContext, get_business_context
from app.db.session import get_db
from app.domain.udhar.service import UdharService
from app.schemas.common import DomainResult
from app.schemas.udhar import (
    ChargeCreate,
    ChargeResponse,
    CustomerCreate,
    CustomerCreateResponse,
    CustomerLedgerResponse,
    CustomerResponse,
    CustomerStatement,
    CustomerUpdate,
    ReminderDraftRequest,
    ReminderDraftResponse,
    RepaymentCreate,
    RepaymentResponse,
    ReversalCreate,
    ReversalResponse,
    UdharSummary,
)

router = APIRouter(prefix="/udhar", tags=["Udhar Management"])


@router.get("/summary", response_model=DomainResult[UdharSummary])
def get_udhar_summary(
    as_of_date: datetime | None = Query(default=None),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DomainResult[UdharSummary]:
    """Retrieve store-wide customer credit metrics, overdue receivables, and aging breakdown."""
    service = UdharService(db, context)
    return service.get_udhar_summary(as_of_date=as_of_date)


@router.get("/customers", response_model=list[CustomerResponse])
def list_customers(
    query: str | None = Query(default=None, description="Search by name or phone"),
    include_archived: bool = Query(default=False, description="Include archived customers"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> list[CustomerResponse]:
    """List customers with derived outstanding balance, overdue amount, and aging status."""
    service = UdharService(db, context)
    return service.list_customers(
        query=query,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/customers",
    response_model=CustomerCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer(
    payload: CustomerCreate,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> CustomerCreateResponse:
    """Create a new customer with optional opening balance, credit limit, and duplicate warnings."""
    service = UdharService(db, context)
    return service.create_customer(payload)


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> CustomerResponse:
    """Retrieve full customer profile with derived balance and aging bucket."""
    service = UdharService(db, context)
    return service.get_customer_detail(customer_id)


@router.put("/customers/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> CustomerResponse:
    """Update customer contact info, credit limit, and reminder consent."""
    service = UdharService(db, context)
    return service.update_customer(customer_id, payload)


@router.post("/customers/{customer_id}/archive", response_model=CustomerResponse)
def archive_customer(
    customer_id: str,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> CustomerResponse:
    """Archive a customer (soft delete)."""
    service = UdharService(db, context)
    return service.archive_customer(customer_id)


@router.post("/customers/{customer_id}/unarchive", response_model=CustomerResponse)
def unarchive_customer(
    customer_id: str,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> CustomerResponse:
    """Restore an archived customer."""
    service = UdharService(db, context)
    return service.unarchive_customer(customer_id)


@router.get("/customers/{customer_id}/ledger", response_model=CustomerLedgerResponse)
def get_customer_ledger(
    customer_id: str,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> CustomerLedgerResponse:
    """Retrieve complete chronological running-balance ledger for a specific customer."""
    service = UdharService(db, context)
    return service.get_customer_ledger(customer_id)


@router.get("/customers/{customer_id}/statement", response_model=DomainResult[CustomerStatement])
def generate_customer_statement(
    customer_id: str,
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DomainResult[CustomerStatement]:
    """Generate an auditable, reconciled customer statement for a specified date interval."""
    service = UdharService(db, context)
    return service.generate_statement(customer_id, start_date=start_date, end_date=end_date)


@router.post(
    "/customers/{customer_id}/reminder-draft",
    response_model=ReminderDraftResponse,
)
def generate_reminder_draft(
    customer_id: str,
    payload: ReminderDraftRequest,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> ReminderDraftResponse:
    """Generate an un-sent reminder preview with WhatsApp link in Hindi, Hinglish, or English.

    Invariant: Preview only. No automated outbound messages are dispatched.
    """
    service = UdharService(db, context)
    return service.generate_reminder_draft(customer_id, language=payload.language)


@router.post(
    "/charges",
    response_model=ChargeResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_charge(
    payload: ChargeCreate,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> ChargeResponse:
    """Record a credit sale / charge against a customer account."""
    service = UdharService(db, context)
    return service.record_charge(payload)


@router.post(
    "/repayments",
    response_model=RepaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_repayment(
    payload: RepaymentCreate,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> RepaymentResponse:
    """Record a customer collection / repayment with FIFO or explicit charge allocations."""
    service = UdharService(db, context)
    return service.record_repayment(payload)


@router.post(
    "/transactions/{transaction_id}/reverse",
    response_model=ReversalResponse,
)
def reverse_transaction(
    transaction_id: str,
    payload: ReversalCreate,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> ReversalResponse:
    """Post an explicit compensating reversal entry referencing an original transaction."""
    service = UdharService(db, context)
    return service.reverse_transaction(transaction_id, reason=payload.reason)
