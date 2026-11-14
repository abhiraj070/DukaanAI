"""Tenant-scoped repository for Customers and Credit Accounts."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_

from app.core.errors import NotFoundError
from app.db.base import utc_now
from app.models.udhar import (
    CreditAccount,
    CreditTransaction,
    Customer,
    TransactionStatus,
    TransactionType,
)
from app.repositories.base import BaseTenantRepository
from app.schemas.udhar import CustomerDuplicateMatch


class CustomerRepository(BaseTenantRepository[Customer]):
    """Tenant-scoped Customer repository."""

    @property
    def model(self) -> type[Customer]:
        return Customer

    def find_duplicates(
        self, display_name: str, phone_e164: str | None = None
    ) -> list[CustomerDuplicateMatch]:
        """Detect possible duplicate customers by phone or name similarity."""
        matches: list[CustomerDuplicateMatch] = []
        name_clean = display_name.strip().lower()

        # 1. Match on phone number if provided
        if phone_e164 and phone_e164.strip():
            phone_clean = phone_e164.strip()
            phone_dupes = self._base_query().filter(Customer.phone_e164 == phone_clean).all()
            for d in phone_dupes:
                matches.append(
                    CustomerDuplicateMatch(
                        existing_customer_id=d.id,
                        existing_display_name=d.display_name,
                        existing_phone=d.phone_e164,
                        match_type="PHONE_MATCH",
                    )
                )

        # 2. Match on name
        existing_matches = {m.existing_customer_id for m in matches}
        name_dupes = self._base_query().filter(Customer.display_name.ilike(name_clean)).all()
        for d in name_dupes:
            if d.id not in existing_matches:
                matches.append(
                    CustomerDuplicateMatch(
                        existing_customer_id=d.id,
                        existing_display_name=d.display_name,
                        existing_phone=d.phone_e164,
                        match_type="EXACT_NAME",
                    )
                )

        return matches

    def create_customer(
        self,
        display_name: str,
        phone_e164: str | None = None,
        notes: str | None = None,
        credit_limit: Decimal | None = None,
        opening_balance: Decimal | None = None,
        opening_balance_due_at: datetime | None = None,
        opening_balance_notes: str | None = None,
    ) -> Customer:
        """Create a new customer, their credit account, and optional opening balance."""
        customer = Customer(
            business_id=self.business_id,
            display_name=display_name.strip(),
            phone_e164=phone_e164.strip() if phone_e164 else None,
            notes=notes,
        )
        self.save(customer)

        # Create linked credit account
        credit_account = CreditAccount(
            business_id=self.business_id,
            customer_id=customer.id,
            credit_limit=credit_limit,
        )
        self.db.add(credit_account)
        self.db.flush()

        # If opening balance is provided and strictly positive, post as opening balance transaction
        if opening_balance is not None and opening_balance > Decimal("0.00"):
            opening_tx = CreditTransaction(
                business_id=self.business_id,
                credit_account_id=credit_account.id,
                transaction_type=TransactionType.OPENING_BALANCE.value,
                amount=opening_balance,
                currency=credit_account.currency,
                description=opening_balance_notes or "Owner-confirmed opening balance",
                reference="OPENING-BALANCE",
                due_at=opening_balance_due_at,
                created_by=self.user_id,
                status=TransactionStatus.CONFIRMED.value,
            )
            self.db.add(opening_tx)
            self.db.flush()

        return customer

    def search_customers(
        self,
        query: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Customer]:
        """Search and filter customers for the tenant."""
        q = self._base_query()
        if not include_archived:
            q = q.filter(Customer.is_active.is_(True))

        if query and query.strip():
            term = f"%{query.strip()}%"
            q = q.filter(
                or_(
                    Customer.display_name.ilike(term),
                    Customer.phone_e164.ilike(term),
                )
            )

        return q.order_by(Customer.display_name.asc()).offset(offset).limit(limit).all()

    def archive_customer(self, customer_id: str) -> Customer:
        """Archive a customer (soft delete)."""
        customer = self.get_by_id_or_fail(customer_id, f"Customer {customer_id} not found")
        customer.is_active = False
        customer.archived_at = utc_now()
        self.db.flush()
        return customer

    def unarchive_customer(self, customer_id: str) -> Customer:
        """Unarchive / restore a customer."""
        customer = self.get_by_id_or_fail(customer_id, f"Customer {customer_id} not found")
        customer.is_active = True
        customer.archived_at = None
        self.db.flush()
        return customer

    def update_customer(
        self,
        customer_id: str,
        display_name: str | None = None,
        phone_e164: str | None = None,
        notes: str | None = None,
        credit_limit: Decimal | None = None,
        reminder_consent_status: str | None = None,
    ) -> Customer:
        """Update customer details and credit limit."""
        customer = self.get_by_id_or_fail(customer_id, f"Customer {customer_id} not found")
        if display_name is not None:
            customer.display_name = display_name.strip()
        if phone_e164 is not None:
            customer.phone_e164 = phone_e164.strip() if phone_e164 else None
        if notes is not None:
            customer.notes = notes
        if reminder_consent_status is not None:
            customer.reminder_consent_status = reminder_consent_status
            if reminder_consent_status == "CONSENTED":
                customer.reminder_consent_at = utc_now()

        if credit_limit is not None or customer.credit_account:
            acc = self.get_credit_account(customer_id)
            if acc and credit_limit is not None:
                acc.credit_limit = credit_limit

        self.db.flush()
        return customer

    def get_credit_account(self, customer_id: str) -> CreditAccount | None:
        """Fetch the credit account for a customer strictly within tenant."""
        return (
            self.db.query(CreditAccount)
            .filter(
                CreditAccount.business_id == self.business_id,
                CreditAccount.customer_id == customer_id,
            )
            .first()
        )

    def get_credit_account_or_fail(self, customer_id: str) -> CreditAccount:
        """Fetch credit account or raise NotFoundError."""
        account = self.get_credit_account(customer_id)
        if not account:
            raise NotFoundError(f"Credit account for customer {customer_id} not found")
        return account
