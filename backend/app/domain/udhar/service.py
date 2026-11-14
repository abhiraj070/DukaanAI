"""Deterministic Udhar Ledger Domain Service."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.core.errors import NotFoundError
from app.models.udhar import (
    CreditAccount,
    CreditAllocation,
    CreditTransaction,
    Customer,
    TransactionStatus,
    TransactionType,
)
from app.repositories.udhar import UdharRepository
from app.schemas.common import DomainResult, EvidenceMetadata, round_curr
from app.schemas.udhar import (
    AgingBucket,
    CustomerStatement,
    StatementLineItem,
    UdharSummary,
)


class UdharService:
    """Service providing authoritative customer credit balances, aging, and statement generation.

    Principles:
    - Receivables are not cash.
    - Authoritative balance derives from the append-only ledger events and allocations.
    - Statements reconcile exactly with the ledger repository.
    """

    def __init__(self, db: Session, context: BusinessContext) -> None:
        self.db = db
        self.context = context
        self.business_id = context.business_id
        self.repo = UdharRepository(db, context)

    def get_udhar_summary(self, as_of_date: datetime | None = None) -> DomainResult[UdharSummary]:
        """Calculate store-wide outstanding udhar receivables and overdue aging distribution."""
        now = as_of_date or datetime.now(UTC)

        # Get all credit accounts for this business
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

        # Aging buckets
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

            # Fetch confirmed charges for this account to compute open amounts per due date
            charges = (
                self.db.query(CreditTransaction)
                .filter(
                    CreditTransaction.credit_account_id == acc.id,
                    CreditTransaction.transaction_type.in_(
                        [
                            TransactionType.CHARGE.value,
                            TransactionType.ADJUSTMENT_DEBIT.value,
                        ]
                    ),
                    CreditTransaction.status != TransactionStatus.REVERSED.value,
                )
                .all()
            )

            for charge in charges:
                source_tx_ids.append(charge.id)
                # Calculate allocated amount to this charge
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
                    charge_amount=round_curr(charge_amt),
                    repayment_amount=round_curr(repay_amt),
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
