"""Tenant-scoped repository for Udhar Ledger transactions and allocations."""

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.audit import AuditLog
from app.models.udhar import (
    CreditAccount,
    CreditAllocation,
    CreditTransaction,
    TransactionStatus,
    TransactionType,
)
from app.repositories.base import BaseTenantRepository


class UdharRepository(BaseTenantRepository[CreditTransaction]):
    """Udhar Ledger repository enforcing append-only financial accounting."""

    @property
    def model(self) -> type[CreditTransaction]:
        return CreditTransaction

    def record_charge(
        self,
        credit_account_id: str,
        amount: Decimal,
        description: str | None = None,
        reference: str | None = None,
        due_at: datetime | None = None,
        idempotency_key: str | None = None,
        metadata_json: str | None = None,
    ) -> CreditTransaction:
        """Record a credit sale / charge entry increasing the customer's balance."""
        return self._record_transaction(
            credit_account_id=credit_account_id,
            transaction_type=TransactionType.CHARGE,
            amount=amount,
            description=description,
            reference=reference,
            due_at=due_at,
            idempotency_key=idempotency_key,
            metadata_json=metadata_json,
        )

    def record_opening_balance(
        self,
        credit_account_id: str,
        amount: Decimal,
        description: str | None = "Owner-confirmed opening balance",
        reference: str | None = "OPENING-BALANCE",
        due_at: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> CreditTransaction:
        """Record an initial opening balance entry increasing customer debt."""
        return self._record_transaction(
            credit_account_id=credit_account_id,
            transaction_type=TransactionType.OPENING_BALANCE,
            amount=amount,
            description=description,
            reference=reference,
            due_at=due_at,
            idempotency_key=idempotency_key,
        )

    def record_repayment(
        self,
        credit_account_id: str,
        amount: Decimal,
        description: str | None = None,
        reference: str | None = None,
        idempotency_key: str | None = None,
        metadata_json: str | None = None,
    ) -> CreditTransaction:
        """Record a collection / repayment entry reducing receivables."""
        return self._record_transaction(
            credit_account_id=credit_account_id,
            transaction_type=TransactionType.REPAYMENT,
            amount=amount,
            description=description,
            reference=reference,
            idempotency_key=idempotency_key,
            metadata_json=metadata_json,
        )

    def _record_transaction(
        self,
        credit_account_id: str,
        transaction_type: TransactionType | str,
        amount: Decimal,
        description: str | None = None,
        reference: str | None = None,
        due_at: datetime | None = None,
        idempotency_key: str | None = None,
        reverses_transaction_id: str | None = None,
        metadata_json: str | None = None,
    ) -> CreditTransaction:
        """Internal helper validating and creating a transaction."""
        if amount <= Decimal("0.00"):
            raise BadRequestError("Ledger transaction amount must be strictly positive")

        # Verify account belongs to tenant
        account = (
            self.db.query(CreditAccount)
            .filter(
                CreditAccount.id == credit_account_id,
                CreditAccount.business_id == self.business_id,
            )
            .first()
        )
        if not account:
            raise NotFoundError(f"Credit account {credit_account_id} not found in this business")

        # Idempotency check
        if idempotency_key:
            existing = (
                self._base_query()
                .filter(CreditTransaction.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                return existing

        type_str = (
            transaction_type.value
            if isinstance(transaction_type, TransactionType)
            else transaction_type
        )

        tx = CreditTransaction(
            business_id=self.business_id,
            credit_account_id=credit_account_id,
            transaction_type=type_str,
            amount=amount,
            currency=account.currency,
            description=description,
            reference=reference,
            due_at=due_at,
            idempotency_key=idempotency_key,
            reverses_transaction_id=reverses_transaction_id,
            metadata_json=metadata_json,
            created_by=self.user_id,
            status=TransactionStatus.CONFIRMED.value,
        )
        return self.save(tx)

    def record_reversal(self, original_transaction_id: str, reason: str) -> CreditTransaction:
        """Record an explicit compensating reversal entry referencing original transaction."""
        original = self.get_by_id_or_fail(
            original_transaction_id, "Original transaction to reverse not found"
        )
        if original.status == TransactionStatus.REVERSED.value:
            raise ConflictError("Transaction has already been reversed")

        # Create reversal transaction of opposite effect or type REVERSAL
        reversal = self._record_transaction(
            credit_account_id=original.credit_account_id,
            transaction_type=TransactionType.REVERSAL,
            amount=original.amount,
            description=f"Reversal of {original.id}: {reason}",
            reference=f"REV-{original.reference or original.id[:8]}",
            reverses_transaction_id=original.id,
            metadata_json=json.dumps({"reason": reason, "reversed_tx_id": original.id}),
        )

        original.status = TransactionStatus.REVERSED.value

        # Clean up allocations attached to this transaction so balances reconcile
        if original.transaction_type == TransactionType.REPAYMENT.value:
            # Delete allocations created by this repayment
            self.db.query(CreditAllocation).filter(
                CreditAllocation.repayment_transaction_id == original.id
            ).delete()
        elif original.transaction_type in (
            TransactionType.CHARGE.value,
            TransactionType.OPENING_BALANCE.value,
            TransactionType.ADJUSTMENT_DEBIT.value,
        ):
            # Delete allocations pointing to this charge
            self.db.query(CreditAllocation).filter(
                CreditAllocation.charge_transaction_id == original.id
            ).delete()

        # Audit log entry
        audit = AuditLog(
            business_id=self.business_id,
            user_id=self.user_id,
            action="REVERSE",
            entity_type="CREDIT_TRANSACTION",
            entity_id=original.id,
            changes_json=json.dumps(
                {
                    "reason": reason,
                    "reversal_id": reversal.id,
                    "amount": str(original.amount),
                    "type": original.transaction_type,
                }
            ),
        )
        self.db.add(audit)
        self.db.flush()
        return reversal

    def allocate_repayment(
        self, repayment_transaction_id: str, charge_transaction_id: str, amount: Decimal
    ) -> CreditAllocation:
        """Allocate a repayment to a specific open charge.

        Invariants:
        1. Allocated amount must be positive.
        2. Repayment and Charge must both belong to this tenant.
        3. Total allocations on the repayment cannot exceed repayment amount.
        4. Total allocations on the charge cannot exceed charge amount.
        """
        if amount <= Decimal("0.00"):
            raise BadRequestError("Allocation amount must be strictly positive")

        repayment = self.get_by_id_or_fail(
            repayment_transaction_id, "Repayment transaction not found"
        )
        if repayment.transaction_type != TransactionType.REPAYMENT.value:
            raise BadRequestError("Source transaction is not a REPAYMENT")
        if repayment.status == TransactionStatus.REVERSED.value:
            raise BadRequestError("Cannot allocate against a reversed repayment")

        charge = self.get_by_id_or_fail(charge_transaction_id, "Charge transaction not found")
        if charge.transaction_type not in (
            TransactionType.CHARGE.value,
            TransactionType.OPENING_BALANCE.value,
            TransactionType.ADJUSTMENT_DEBIT.value,
        ):
            raise BadRequestError("Target transaction is not a CHARGE or OPENING_BALANCE")
        if charge.status == TransactionStatus.REVERSED.value:
            raise BadRequestError("Cannot allocate against a reversed charge")

        if repayment.credit_account_id != charge.credit_account_id:
            raise BadRequestError("Repayment and charge belong to different customer accounts")

        # Check existing allocations for repayment
        existing_repayment_allocated = (
            self.db.query(
                func.coalesce(func.sum(CreditAllocation.allocated_amount), Decimal("0.00"))
            )
            .filter(CreditAllocation.repayment_transaction_id == repayment_transaction_id)
            .scalar()
        )
        if existing_repayment_allocated + amount > repayment.amount:
            rem = repayment.amount - existing_repayment_allocated
            raise BadRequestError(
                f"Allocation exceeds available repayment amount (Remaining: {rem})"
            )

        # Check existing allocations for charge
        existing_charge_allocated = (
            self.db.query(
                func.coalesce(func.sum(CreditAllocation.allocated_amount), Decimal("0.00"))
            )
            .filter(CreditAllocation.charge_transaction_id == charge_transaction_id)
            .scalar()
        )
        if existing_charge_allocated + amount > charge.amount:
            rem_charge = charge.amount - existing_charge_allocated
            raise BadRequestError(
                f"Allocation exceeds open charge amount (Remaining: {rem_charge})"
            )

        allocation = CreditAllocation(
            business_id=self.business_id,
            repayment_transaction_id=repayment_transaction_id,
            charge_transaction_id=charge_transaction_id,
            allocated_amount=amount,
        )
        self.db.add(allocation)
        self.db.flush()
        return allocation

    def get_open_charges(self, credit_account_id: str) -> list[tuple[CreditTransaction, Decimal]]:
        """Fetch active charges with unallocated open balances in FIFO order."""
        charges = (
            self._base_query()
            .filter(
                CreditTransaction.credit_account_id == credit_account_id,
                CreditTransaction.transaction_type.in_(
                    [
                        TransactionType.CHARGE.value,
                        TransactionType.OPENING_BALANCE.value,
                        TransactionType.ADJUSTMENT_DEBIT.value,
                    ]
                ),
                CreditTransaction.status != TransactionStatus.REVERSED.value,
            )
            .order_by(CreditTransaction.transaction_at.asc())
            .all()
        )

        open_charges: list[tuple[CreditTransaction, Decimal]] = []
        for ch in charges:
            allocated = (
                self.db.query(
                    func.coalesce(func.sum(CreditAllocation.allocated_amount), Decimal("0.00"))
                )
                .filter(CreditAllocation.charge_transaction_id == ch.id)
                .scalar()
            )
            open_amt = ch.amount - allocated
            if open_amt > Decimal("0.00"):
                open_charges.append((ch, open_amt))

        return open_charges

    def auto_allocate_repayment(self, repayment_transaction_id: str) -> list[CreditAllocation]:
        """Automatically allocate repayment across open charges in FIFO order."""
        repayment = self.get_by_id_or_fail(
            repayment_transaction_id, "Repayment transaction not found"
        )
        if repayment.transaction_type != TransactionType.REPAYMENT.value:
            raise BadRequestError("Source transaction is not a REPAYMENT")
        if repayment.status == TransactionStatus.REVERSED.value:
            raise BadRequestError("Cannot allocate a reversed repayment")

        # Existing allocated amount
        already_allocated = (
            self.db.query(
                func.coalesce(func.sum(CreditAllocation.allocated_amount), Decimal("0.00"))
            )
            .filter(CreditAllocation.repayment_transaction_id == repayment_transaction_id)
            .scalar()
        )
        remaining_repayment = repayment.amount - already_allocated
        if remaining_repayment <= Decimal("0.00"):
            return []

        open_charges = self.get_open_charges(repayment.credit_account_id)
        allocations: list[CreditAllocation] = []

        for ch, open_balance in open_charges:
            if remaining_repayment <= Decimal("0.00"):
                break

            alloc_amt = min(remaining_repayment, open_balance)
            alloc = self.allocate_repayment(
                repayment_transaction_id=repayment.id,
                charge_transaction_id=ch.id,
                amount=alloc_amt,
            )
            allocations.append(alloc)
            remaining_repayment -= alloc_amt

        return allocations

    def get_account_balance(self, credit_account_id: str) -> Decimal:
        """Derive outstanding balance from all confirmed transactions.

        Formula:
        outstanding = (charges + opening + debit adjustments)
                      - (repayments + credit adjustments)
        Compensating reversals directly offset their referenced transaction.
        """
        transactions = (
            self._base_query()
            .filter(CreditTransaction.credit_account_id == credit_account_id)
            .all()
        )

        balance = Decimal("0.00")
        for tx in transactions:
            if tx.transaction_type in (
                TransactionType.CHARGE.value,
                TransactionType.OPENING_BALANCE.value,
                TransactionType.ADJUSTMENT_DEBIT.value,
            ):
                balance += tx.amount
            elif tx.transaction_type in (
                TransactionType.REPAYMENT.value,
                TransactionType.ADJUSTMENT_CREDIT.value,
            ):
                balance -= tx.amount
            elif tx.transaction_type == TransactionType.REVERSAL.value:
                # Compensating reversal offsets the referenced original transaction
                if tx.reverses_transaction_id:
                    orig = self.get_by_id(tx.reverses_transaction_id)
                    if orig and orig.transaction_type in (
                        TransactionType.CHARGE.value,
                        TransactionType.OPENING_BALANCE.value,
                        TransactionType.ADJUSTMENT_DEBIT.value,
                    ):
                        balance -= tx.amount
                    elif orig and orig.transaction_type in (
                        TransactionType.REPAYMENT.value,
                        TransactionType.ADJUSTMENT_CREDIT.value,
                    ):
                        balance += tx.amount

        return balance
