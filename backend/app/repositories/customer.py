"""Tenant-scoped repository for Customers and Credit Accounts."""

from decimal import Decimal

from app.core.errors import NotFoundError
from app.models.udhar import CreditAccount, Customer
from app.repositories.base import BaseTenantRepository


class CustomerRepository(BaseTenantRepository[Customer]):
    """Tenant-scoped Customer repository."""

    @property
    def model(self) -> type[Customer]:
        return Customer

    def create_customer(
        self,
        display_name: str,
        phone_e164: str | None = None,
        notes: str | None = None,
        credit_limit: Decimal | None = None,
    ) -> Customer:
        """Create a new customer and initialize their credit account."""
        customer = Customer(
            business_id=self.business_id,
            display_name=display_name,
            phone_e164=phone_e164,
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
