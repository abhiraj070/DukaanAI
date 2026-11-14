"""Deterministic Udhar Ledger Domain Service."""

import json
import urllib.parse
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.core.errors import NotFoundError
from app.models.audit import AuditLog
from app.models.identity import Business
from app.models.udhar import (
    CreditAccount,
    CreditAllocation,
    CreditTransaction,
    Customer,
    TransactionStatus,
    TransactionType,
)
from app.repositories.customer import CustomerRepository
from app.repositories.udhar import UdharRepository
from app.schemas.common import DomainResult, EvidenceMetadata, round_curr
from app.schemas.udhar import (
    AgingBucket,
    AllocationResponse,
    ChargeCreate,
    ChargeResponse,
    CustomerCreate,
    CustomerCreateResponse,
    CustomerLedgerResponse,
    CustomerResponse,
    CustomerStatement,
    CustomerUpdate,
    ReminderDraftResponse,
    RepaymentCreate,
    RepaymentResponse,
    ReversalResponse,
    StatementLineItem,
    UdharSummary,
)


class UdharService:
    """Authoritative service for customer credit management, ledger accounting, and statements.

    Principles:
    - Receivables are not cash.
    - Authoritative balance derives from the append-only ledger events and allocations.
    - Statements reconcile exactly with the ledger repository.
    - Repayments are collections against receivables, never sales revenue.
    """

    def __init__(self, db: Session, context: BusinessContext) -> None:
        self.db = db
        self.context = context
        self.business_id = context.business_id
        self.repo = UdharRepository(db, context)
        self.customer_repo = CustomerRepository(db, context)

    # ---------------------------------------------------------
    # Store-Wide Udhar Summary & Aging Distribution
    # ---------------------------------------------------------

    def get_udhar_summary(self, as_of_date: datetime | None = None) -> DomainResult[UdharSummary]:
        """Calculate store-wide outstanding udhar receivables and overdue aging distribution."""
        now = as_of_date or datetime.now(UTC)

        accounts = (
            self.db.query(CreditAccount)
            .filter(
                CreditAccount.business_id == self.business_id, CreditAccount.is_active.is_(True)
            )
            .all()
        )

        total_receivables = Decimal("0.00")
        total_overdue = Decimal("0.00")
        active_debt_customers = 0

        buckets = {
            "NOT_DUE": {
                "label": "Current / Not Due",
                "amount": Decimal("0.00"),
                "customers": set(),
            },
            "1_7_DAYS": {
                "label": "1–7 Days Overdue",
                "amount": Decimal("0.00"),
                "customers": set(),
            },
            "8_30_DAYS": {
                "label": "8–30 Days Overdue",
                "amount": Decimal("0.00"),
                "customers": set(),
            },
            "31_60_DAYS": {
                "label": "31–60 Days Overdue",
                "amount": Decimal("0.00"),
                "customers": set(),
            },
            "60_PLUS_DAYS": {
                "label": "60+ Days Overdue",
                "amount": Decimal("0.00"),
                "customers": set(),
            },
        }

        source_tx_ids = []

        for acc in accounts:
            balance = self.repo.get_account_balance(acc.id)
            if balance > Decimal("0.00"):
                total_receivables += balance
                active_debt_customers += 1

            # Fetch confirmed charges and opening balances for this account
            charges = (
                self.db.query(CreditTransaction)
                .filter(
                    CreditTransaction.credit_account_id == acc.id,
                    CreditTransaction.transaction_type.in_(
                        [
                            TransactionType.CHARGE.value,
                            TransactionType.OPENING_BALANCE.value,
                            TransactionType.ADJUSTMENT_DEBIT.value,
                        ]
                    ),
                    CreditTransaction.status != TransactionStatus.REVERSED.value,
                )
                .all()
            )

            for charge in charges:
                source_tx_ids.append(charge.id)
                allocated = (
                    self.db.query(
                        func.coalesce(func.sum(CreditAllocation.allocated_amount), Decimal("0.00"))
                    )
                    .filter(CreditAllocation.charge_transaction_id == charge.id)
                    .scalar()
                )
                open_balance = charge.amount - allocated

                if open_balance > Decimal("0.00"):
                    due = charge.due_at
                    if due is not None and due.tzinfo is None:
                        due = due.replace(tzinfo=UTC)
                    curr_now = now if now.tzinfo is not None else now.replace(tzinfo=UTC)

                    if due is None or due > curr_now:
                        bucket_key = "NOT_DUE"
                    else:
                        days_overdue = (curr_now - due).days
                        total_overdue += open_balance
                        if days_overdue <= 7:
                            bucket_key = "1_7_DAYS"
                        elif days_overdue <= 30:
                            bucket_key = "8_30_DAYS"
                        elif days_overdue <= 60:
                            bucket_key = "31_60_DAYS"
                        else:
                            bucket_key = "60_PLUS_DAYS"

                    buckets[bucket_key]["amount"] += open_balance
                    buckets[bucket_key]["customers"].add(acc.customer_id)

        aging_list = [
            AgingBucket(
                bucket_key=k,
                label=v["label"],
                amount=round_curr(v["amount"]),
                customer_count=len(v["customers"]),
            )
            for k, v in buckets.items()
        ]

        summary = UdharSummary(
            total_receivables=round_curr(total_receivables),
            overdue_amount=round_curr(total_overdue),
            customers_with_balance_count=active_debt_customers,
            aging_buckets=aging_list,
            currency=self.context.currency,
        )

        evidence = EvidenceMetadata(
            source_record_ids=source_tx_ids[:100],
            calculation_method="ledger_allocation_aging",
            assumptions=[
                "Charges with no explicit due date classified as Current (Not Due)",
                "Open receivables derived after subtracting allocated repayments",
            ],
            freshness_timestamp=datetime.now(UTC),
            warnings=[],
        )

        return DomainResult(data=summary, evidence=evidence)

    # ---------------------------------------------------------
    # Customer Directory & Management
    # ---------------------------------------------------------

    def get_customer_detail(self, customer_id: str) -> CustomerResponse:
        """Fetch full customer record with derived balance, overdue status, and aging bucket."""
        customer = (
            self.db.query(Customer)
            .filter(Customer.id == customer_id, Customer.business_id == self.business_id)
            .first()
        )
        if not customer:
            raise NotFoundError(f"Customer {customer_id} not found in this business")

        account = customer.credit_account
        if not account:
            raise NotFoundError(f"Credit account for customer {customer_id} not found")

        balance = self.repo.get_account_balance(account.id)

        # Calculate overdue amount and aging bucket
        now = datetime.now(UTC)
        charges = (
            self.db.query(CreditTransaction)
            .filter(
                CreditTransaction.credit_account_id == account.id,
                CreditTransaction.transaction_type.in_(
                    [
                        TransactionType.CHARGE.value,
                        TransactionType.OPENING_BALANCE.value,
                        TransactionType.ADJUSTMENT_DEBIT.value,
                    ]
                ),
                CreditTransaction.status != TransactionStatus.REVERSED.value,
            )
            .all()
        )

        overdue_amt = Decimal("0.00")
        worst_bucket = "NOT_DUE"
        max_days_overdue = -1

        for ch in charges:
            allocated = (
                self.db.query(
                    func.coalesce(func.sum(CreditAllocation.allocated_amount), Decimal("0.00"))
                )
                .filter(CreditAllocation.charge_transaction_id == ch.id)
                .scalar()
            )
            open_amt = ch.amount - allocated
            if open_amt > Decimal("0.00") and ch.due_at:
                due = ch.due_at if ch.due_at.tzinfo is not None else ch.due_at.replace(tzinfo=UTC)
                if due <= now:
                    overdue_amt += open_amt
                    days = (now - due).days
                    if days > max_days_overdue:
                        max_days_overdue = days

        if max_days_overdue > 60:
            worst_bucket = "60_PLUS_DAYS"
        elif max_days_overdue > 30:
            worst_bucket = "31_60_DAYS"
        elif max_days_overdue > 7:
            worst_bucket = "8_30_DAYS"
        elif max_days_overdue >= 0:
            worst_bucket = "1_7_DAYS"

        tx_count = (
            self.db.query(CreditTransaction)
            .filter(CreditTransaction.credit_account_id == account.id)
            .count()
        )

        return CustomerResponse(
            id=customer.id,
            display_name=customer.display_name,
            phone_e164=customer.phone_e164,
            notes=customer.notes,
            credit_limit=account.credit_limit,
            currency=account.currency,
            is_active=customer.is_active,
            reminder_consent_status=customer.reminder_consent_status,
            created_at=customer.created_at,
            archived_at=customer.archived_at,
            outstanding_balance=round_curr(balance),
            overdue_amount=round_curr(overdue_amt),
            aging_bucket=worst_bucket,
            transaction_count=tx_count,
        )

    def list_customers(
        self,
        query: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CustomerResponse]:
        """List customers with derived financial summaries."""
        customers = self.customer_repo.search_customers(
            query=query,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
        return [self.get_customer_detail(c.id) for c in customers]

    def create_customer(self, payload: CustomerCreate) -> CustomerCreateResponse:
        """Create a new customer, initialize credit account, and check for duplicate warnings."""
        dupes = self.customer_repo.find_duplicates(payload.display_name, payload.phone_e164)
        warnings: list[str] = []
        if dupes:
            names = ", ".join(d.existing_display_name for d in dupes)
            warnings.append(f"Possible duplicate customer(s) found matching name or phone: {names}")

        customer = self.customer_repo.create_customer(
            display_name=payload.display_name,
            phone_e164=payload.phone_e164,
            notes=payload.notes,
            credit_limit=payload.credit_limit,
            opening_balance=payload.opening_balance,
            opening_balance_due_at=payload.opening_balance_due_at,
            opening_balance_notes=payload.opening_balance_notes,
        )

        # Audit log entry
        audit = AuditLog(
            business_id=self.business_id,
            user_id=self.context.user_id,
            action="CREATE",
            entity_type="CUSTOMER",
            entity_id=customer.id,
            changes_json=json.dumps(
                {
                    "display_name": customer.display_name,
                    "phone_e164": customer.phone_e164,
                    "credit_limit": str(payload.credit_limit) if payload.credit_limit else None,
                    "opening_balance": (
                        str(payload.opening_balance) if payload.opening_balance else None
                    ),
                }
            ),
        )
        self.db.add(audit)
        self.db.flush()

        detail = self.get_customer_detail(customer.id)
        return CustomerCreateResponse(
            customer=detail,
            warnings=warnings,
            duplicate_matches=dupes,
        )

    def update_customer(self, customer_id: str, payload: CustomerUpdate) -> CustomerResponse:
        """Update customer details and credit limit."""
        customer = self.customer_repo.update_customer(
            customer_id=customer_id,
            display_name=payload.display_name,
            phone_e164=payload.phone_e164,
            notes=payload.notes,
            credit_limit=payload.credit_limit,
            reminder_consent_status=payload.reminder_consent_status,
        )

        audit = AuditLog(
            business_id=self.business_id,
            user_id=self.context.user_id,
            action="UPDATE",
            entity_type="CUSTOMER",
            entity_id=customer.id,
            changes_json=json.dumps(
                {
                    "display_name": payload.display_name,
                    "credit_limit": str(payload.credit_limit) if payload.credit_limit else None,
                }
            ),
        )
        self.db.add(audit)
        self.db.flush()

        return self.get_customer_detail(customer_id)

    def archive_customer(self, customer_id: str) -> CustomerResponse:
        """Archive a customer (soft-delete)."""
        customer = self.customer_repo.archive_customer(customer_id)
        audit = AuditLog(
            business_id=self.business_id,
            user_id=self.context.user_id,
            action="ARCHIVE",
            entity_type="CUSTOMER",
            entity_id=customer.id,
        )
        self.db.add(audit)
        self.db.flush()
        return self.get_customer_detail(customer_id)

    def unarchive_customer(self, customer_id: str) -> CustomerResponse:
        """Restore an archived customer."""
        customer = self.customer_repo.unarchive_customer(customer_id)
        audit = AuditLog(
            business_id=self.business_id,
            user_id=self.context.user_id,
            action="UNARCHIVE",
            entity_type="CUSTOMER",
            entity_id=customer.id,
        )
        self.db.add(audit)
        self.db.flush()
        return self.get_customer_detail(customer_id)

    # ---------------------------------------------------------
    # Ledger Transactions: Charges, Repayments & Reversals
    # ---------------------------------------------------------

    def record_charge(self, payload: ChargeCreate) -> ChargeResponse:
        """Record a credit sale / charge entry with credit limit validation."""
        account = self.customer_repo.get_credit_account_or_fail(payload.customer_id)

        # Check current balance and warn if exceeding credit limit
        current_balance = self.repo.get_account_balance(account.id)
        credit_limit_warning: str | None = None
        if account.credit_limit is not None:
            new_estimated = current_balance + payload.amount
            if new_estimated > account.credit_limit:
                credit_limit_warning = (
                    f"Warning: Charge of ₹{payload.amount} exceeds customer credit limit of "
                    f"₹{account.credit_limit} (New balance: ₹{new_estimated})"
                )

        tx = self.repo.record_charge(
            credit_account_id=account.id,
            amount=payload.amount,
            description=payload.description,
            reference=payload.reference,
            due_at=payload.due_at,
            idempotency_key=payload.idempotency_key,
        )

        audit = AuditLog(
            business_id=self.business_id,
            user_id=self.context.user_id,
            action="CREATE",
            entity_type="CREDIT_TRANSACTION",
            entity_id=tx.id,
            changes_json=json.dumps(
                {
                    "type": tx.transaction_type,
                    "amount": str(tx.amount),
                    "customer_id": payload.customer_id,
                }
            ),
        )
        self.db.add(audit)
        self.db.flush()

        new_balance = self.repo.get_account_balance(account.id)

        return ChargeResponse(
            transaction_id=tx.id,
            customer_id=payload.customer_id,
            amount=round_curr(tx.amount),
            transaction_type=tx.transaction_type,
            transaction_at=tx.transaction_at,
            due_at=tx.due_at,
            description=tx.description,
            reference=tx.reference,
            status=tx.status,
            credit_limit_warning=credit_limit_warning,
            new_balance=round_curr(new_balance),
        )

    def record_repayment(self, payload: RepaymentCreate) -> RepaymentResponse:
        """Record a customer collection / repayment with automatic or manual allocations.

        Invariant: Repayments reduce customer receivables through explicit allocations.
        Repayments are NOT sales revenue.
        """
        account = self.customer_repo.get_credit_account_or_fail(payload.customer_id)

        meta = json.dumps({"payment_mode": payload.payment_mode})
        tx = self.repo.record_repayment(
            credit_account_id=account.id,
            amount=payload.amount,
            description=payload.description,
            reference=payload.reference,
            idempotency_key=payload.idempotency_key,
            metadata_json=meta,
        )

        allocations: list[CreditAllocation] = []

        # 1. Manual allocations if provided
        if payload.allocations:
            for alloc_input in payload.allocations:
                alloc = self.repo.allocate_repayment(
                    repayment_transaction_id=tx.id,
                    charge_transaction_id=alloc_input.charge_transaction_id,
                    amount=alloc_input.amount,
                )
                allocations.append(alloc)

        # 2. Auto-allocate remaining balance in FIFO order if requested
        if payload.auto_allocate:
            auto_allocs = self.repo.auto_allocate_repayment(tx.id)
            allocations.extend(auto_allocs)

        total_allocated = sum((a.allocated_amount for a in allocations), Decimal("0.00"))
        unallocated = tx.amount - total_allocated

        audit = AuditLog(
            business_id=self.business_id,
            user_id=self.context.user_id,
            action="CREATE",
            entity_type="CREDIT_TRANSACTION",
            entity_id=tx.id,
            changes_json=json.dumps(
                {
                    "type": tx.transaction_type,
                    "amount": str(tx.amount),
                    "customer_id": payload.customer_id,
                    "payment_mode": payload.payment_mode,
                    "allocated": str(total_allocated),
                }
            ),
        )
        self.db.add(audit)
        self.db.flush()

        new_balance = self.repo.get_account_balance(account.id)

        alloc_responses = [
            AllocationResponse(
                id=a.id,
                charge_transaction_id=a.charge_transaction_id,
                allocated_amount=round_curr(a.allocated_amount),
                created_at=a.created_at,
            )
            for a in allocations
        ]

        return RepaymentResponse(
            transaction_id=tx.id,
            customer_id=payload.customer_id,
            amount=round_curr(tx.amount),
            payment_mode=payload.payment_mode,
            transaction_at=tx.transaction_at,
            reference=tx.reference,
            status=tx.status,
            allocated_amount=round_curr(total_allocated),
            unallocated_amount=round_curr(unallocated),
            allocations=alloc_responses,
            new_balance=round_curr(new_balance),
        )

    def reverse_transaction(self, transaction_id: str, reason: str) -> ReversalResponse:
        """Create a compensating reversal transaction."""
        reversal = self.repo.record_reversal(transaction_id, reason)
        new_balance = self.repo.get_account_balance(reversal.credit_account_id)

        return ReversalResponse(
            reversal_transaction_id=reversal.id,
            original_transaction_id=transaction_id,
            amount=round_curr(reversal.amount),
            reversed_at=reversal.transaction_at,
            new_balance=round_curr(new_balance),
        )

    # ---------------------------------------------------------
    # Ledger & Statement Generation
    # ---------------------------------------------------------

    def generate_statement(
        self,
        customer_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> DomainResult[CustomerStatement]:
        """Generate an auditable, reconciled customer statement."""
        customer = (
            self.db.query(Customer)
            .filter(Customer.id == customer_id, Customer.business_id == self.business_id)
            .first()
        )
        if not customer:
            raise NotFoundError(f"Customer {customer_id} not found in this business")

        account = customer.credit_account
        if not account:
            raise NotFoundError(f"Credit account for customer {customer_id} not found")

        # 1. Compute opening balance prior to start_date
        opening_balance = Decimal("0.00")
        if start_date:
            prior_txs = (
                self.db.query(CreditTransaction)
                .filter(
                    CreditTransaction.credit_account_id == account.id,
                    CreditTransaction.transaction_at < start_date,
                )
                .all()
            )
            for tx in prior_txs:
                if tx.transaction_type in (
                    TransactionType.CHARGE.value,
                    TransactionType.OPENING_BALANCE.value,
                    TransactionType.ADJUSTMENT_DEBIT.value,
                ):
                    opening_balance += tx.amount
                elif tx.transaction_type in (
                    TransactionType.REPAYMENT.value,
                    TransactionType.ADJUSTMENT_CREDIT.value,
                ):
                    opening_balance -= tx.amount
                elif (
                    tx.transaction_type == TransactionType.REVERSAL.value
                    and tx.reverses_transaction_id
                ):
                    orig = self.repo.get_by_id(tx.reverses_transaction_id)
                    if orig and orig.transaction_type in (
                        TransactionType.CHARGE.value,
                        TransactionType.OPENING_BALANCE.value,
                        TransactionType.ADJUSTMENT_DEBIT.value,
                    ):
                        opening_balance -= tx.amount
                    elif orig and orig.transaction_type in (
                        TransactionType.REPAYMENT.value,
                        TransactionType.ADJUSTMENT_CREDIT.value,
                    ):
                        opening_balance += tx.amount

        # 2. Query transactions in window
        tx_query = self.db.query(CreditTransaction).filter(
            CreditTransaction.credit_account_id == account.id
        )
        if start_date:
            tx_query = tx_query.filter(CreditTransaction.transaction_at >= start_date)
        if end_date:
            tx_query = tx_query.filter(CreditTransaction.transaction_at <= end_date)

        transactions = tx_query.order_by(CreditTransaction.transaction_at.asc()).all()

        running_balance = opening_balance
        total_charges = Decimal("0.00")
        total_repayments = Decimal("0.00")
        lines: list[StatementLineItem] = []

        for tx in transactions:
            charge_amt = None
            repay_amt = None

            if tx.transaction_type in (
                TransactionType.CHARGE.value,
                TransactionType.OPENING_BALANCE.value,
                TransactionType.ADJUSTMENT_DEBIT.value,
            ):
                charge_amt = tx.amount
                running_balance += tx.amount
                total_charges += tx.amount
            elif tx.transaction_type in (
                TransactionType.REPAYMENT.value,
                TransactionType.ADJUSTMENT_CREDIT.value,
            ):
                repay_amt = tx.amount
                running_balance -= tx.amount
                total_repayments += tx.amount
            elif tx.transaction_type == TransactionType.REVERSAL.value:
                if tx.reverses_transaction_id:
                    orig = self.repo.get_by_id(tx.reverses_transaction_id)
                    if orig and orig.transaction_type in (
                        TransactionType.CHARGE.value,
                        TransactionType.OPENING_BALANCE.value,
                        TransactionType.ADJUSTMENT_DEBIT.value,
                    ):
                        repay_amt = tx.amount
                        running_balance -= tx.amount
                    elif orig and orig.transaction_type in (
                        TransactionType.REPAYMENT.value,
                        TransactionType.ADJUSTMENT_CREDIT.value,
                    ):
                        charge_amt = tx.amount
                        running_balance += tx.amount

            lines.append(
                StatementLineItem(
                    transaction_id=tx.id,
                    transaction_at=tx.transaction_at,
                    transaction_type=tx.transaction_type,
                    description=tx.description,
                    reference=tx.reference,
                    charge_amount=round_curr(charge_amt) if charge_amt is not None else None,
                    repayment_amount=round_curr(repay_amt) if repay_amt is not None else None,
                    running_balance=round_curr(running_balance),
                )
            )

        statement = CustomerStatement(
            customer_id=customer.id,
            customer_name=customer.display_name,
            phone=customer.phone_e164,
            currency=account.currency,
            start_date=start_date,
            end_date=end_date,
            opening_balance=round_curr(opening_balance),
            total_charges=round_curr(total_charges),
            total_repayments=round_curr(total_repayments),
            closing_balance=round_curr(running_balance),
            lines=lines,
        )

        evidence = EvidenceMetadata(
            source_record_ids=[tx.id for tx in transactions],
            date_window_start=start_date,
            date_window_end=end_date,
            calculation_method="chronological_ledger_reconciliation",
            assumptions=["Running balance computed strictly by transaction event order"],
            freshness_timestamp=datetime.now(UTC),
            warnings=[],
        )

        return DomainResult(data=statement, evidence=evidence)

    def get_customer_ledger(self, customer_id: str) -> CustomerLedgerResponse:
        """Get complete running-balance ledger for a specific customer."""
        customer = (
            self.db.query(Customer)
            .filter(Customer.id == customer_id, Customer.business_id == self.business_id)
            .first()
        )
        if not customer:
            raise NotFoundError(f"Customer {customer_id} not found in this business")

        account = self.customer_repo.get_credit_account_or_fail(customer_id)
        statement_res = self.generate_statement(customer_id)
        statement = statement_res.data

        return CustomerLedgerResponse(
            customer_id=customer.id,
            customer_name=customer.display_name,
            outstanding_balance=statement.closing_balance,
            credit_limit=account.credit_limit,
            currency=account.currency,
            lines=statement.lines,
        )

    # ---------------------------------------------------------
    # Polite Reminder Draft Generation (Un-sent Preview Only)
    # ---------------------------------------------------------

    def generate_reminder_draft(
        self, customer_id: str, language: str = "Hinglish"
    ) -> ReminderDraftResponse:
        """Generate a polite reminder draft with WhatsApp click-to-chat link.

        Invariant: Text preview only. No automated outbound messages are sent.
        """
        detail = self.get_customer_detail(customer_id)

        biz = self.db.query(Business).filter(Business.id == self.business_id).first()
        biz_name = biz.name if biz else "Dukaan"

        # Determine nearest due date from open charges
        acct = self.customer_repo.get_credit_account_or_fail(customer_id)
        charges = (
            self.db.query(CreditTransaction)
            .filter(
                CreditTransaction.credit_account_id == acct.id,
                CreditTransaction.transaction_type.in_(
                    [TransactionType.CHARGE.value, TransactionType.OPENING_BALANCE.value]
                ),
                CreditTransaction.status != TransactionStatus.REVERSED.value,
                CreditTransaction.due_at.isnot(None),
            )
            .order_by(CreditTransaction.due_at.asc())
            .first()
        )
        due_at = charges.due_at if charges else None

        due_date_str = due_at.strftime("%d-%b-%Y") if due_at else ""

        if language == "Hindi":
            due_part = f" जिसकी अंतिम तिथि {due_date_str} थी।" if due_at else ""
            draft = (
                f"नमस्ते {detail.display_name} जी, आपका {biz_name} पर कुल बकाया उधार "
                f"₹{detail.outstanding_balance} है{due_part}। कृपया समय पर भुगतान करने की कृपा करें। "
                f"धन्यवाद!"
            )
        elif language == "English":
            due_part = f" which was due on {due_date_str}." if due_at else "."
            draft = (
                f"Dear {detail.display_name}, this is a gentle reminder regarding your "
                f"outstanding balance of ₹{detail.outstanding_balance} at {biz_name}{due_part} "
                f"Kindly settle the dues at your earliest convenience. Thank you!"
            )
        else:  # Hinglish default
            due_part = f" jo {due_date_str} ko due tha." if due_at else "."
            draft = (
                f"Namaste {detail.display_name} ji, aapka {biz_name} par kul bakaya udhar "
                f"₹{detail.outstanding_balance} hai{due_part} Kripya samay par bhuqtan karein. "
                f"Dhanyawaad!"
            )

        whatsapp_link: str | None = None
        if detail.phone_e164:
            clean_digits = "".join(filter(str.isdigit, detail.phone_e164))
            # Format Indian 10-digit to 91XXXXXXXXXX
            if len(clean_digits) == 10:
                clean_digits = f"91{clean_digits}"
            whatsapp_link = f"https://api.whatsapp.com/send?phone={clean_digits}&text={urllib.parse.quote(draft)}"

        disclaimer = (
            "This is an un-sent preview draft. DukesAI does not send automated outbound messages "
            "without verified WhatsApp/SMS integration and explicit customer consent."
        )

        return ReminderDraftResponse(
            customer_id=detail.id,
            customer_name=detail.display_name,
            phone=detail.phone_e164,
            outstanding_balance=detail.outstanding_balance,
            overdue_amount=detail.overdue_amount,
            due_at=due_at,
            language=language,
            draft_text=draft,
            whatsapp_link=whatsapp_link,
            consent_status=detail.reminder_consent_status,
            disclaimer=disclaimer,
        )
