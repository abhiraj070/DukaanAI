"""Comprehensive cross-tenant security and authorization isolation tests."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.context import get_business_context
from app.core.errors import ForbiddenError, NotFoundError
from app.models.catalogue import Product
from app.repositories.customer import CustomerRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.product import ProductRepository
from app.repositories.udhar import UdharRepository


def test_cross_tenant_product_isolation(db_session: Session, tenants: dict):
    """Verify Tenant B cannot read, list, or access Tenant A's products."""
    tenants["tenant_a"]["context"]
    ctx_b = tenants["tenant_b"]["context"]
    prod_a = tenants["tenant_a"]["product"]
    prod_b = tenants["tenant_b"]["product"]

    repo_b = ProductRepository(db_session, ctx_b)

    # 1. Direct get_by_id of Tenant A's product via Tenant B's repository must return None
    assert repo_b.get_by_id(prod_a.id) is None

    # 2. list_all must only return Tenant B's products
    b_products = repo_b.list_all()
    b_product_ids = [p.id for p in b_products]
    assert prod_b.id in b_product_ids
    assert prod_a.id not in b_product_ids

    # 3. get_by_id_or_fail raises NotFoundError
    with pytest.raises(NotFoundError):
        repo_b.get_by_id_or_fail(prod_a.id)


def test_cross_tenant_product_mutation_protection(db_session: Session, tenants: dict):
    """Verify Tenant B cannot delete or overwrite Tenant A's products."""
    ctx_a = tenants["tenant_a"]["context"]
    ctx_b = tenants["tenant_b"]["context"]
    prod_a = tenants["tenant_a"]["product"]

    repo_b = ProductRepository(db_session, ctx_b)

    # Deleting Tenant A's product through Tenant B's repository fails safely
    deleted = repo_b.delete(prod_a.id)
    assert deleted is False

    # Verify prod_a still exists in Tenant A
    repo_a = ProductRepository(db_session, ctx_a)
    assert repo_a.get_by_id(prod_a.id) is not None

    # Attempting to save an entity with a mismatched business_id triggers ForbiddenError
    alien_product = Product(
        business_id=ctx_a.business_id,  # Spoofed business_id
        name="Malicious Injected Product",
        selling_price=Decimal("100.00"),
    )
    with pytest.raises(ForbiddenError):
        repo_b.save(alien_product)


def test_cross_tenant_customer_and_credit_isolation(db_session: Session, tenants: dict):
    """Verify customer profiles and credit accounts cannot leak across tenants."""
    ctx_b = tenants["tenant_b"]["context"]
    cust_a = tenants["tenant_a"]["customer"]
    tenants["tenant_a"]["credit_account"]

    repo_cust_b = CustomerRepository(db_session, ctx_b)

    # Tenant B cannot read Tenant A's customer
    assert repo_cust_b.get_by_id(cust_a.id) is None
    assert repo_cust_b.get_credit_account(cust_a.id) is None

    with pytest.raises(NotFoundError):
        repo_cust_b.get_credit_account_or_fail(cust_a.id)


def test_cross_tenant_udhar_ledger_isolation(db_session: Session, tenants: dict):
    """Verify Udhar transactions and allocations are strictly tenant-isolated."""
    ctx_a = tenants["tenant_a"]["context"]
    ctx_b = tenants["tenant_b"]["context"]
    acc_a = tenants["tenant_a"]["credit_account"]
    acc_b = tenants["tenant_b"]["credit_account"]

    udhar_a = UdharRepository(db_session, ctx_a)
    udhar_b = UdharRepository(db_session, ctx_b)

    # Record a charge in Tenant A
    charge_a = udhar_a.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("1200.00"),
        description="Tenant A Grocery Credit",
    )
    assert charge_a.business_id == ctx_a.business_id

    # Tenant B cannot see Tenant A's charge
    assert udhar_b.get_by_id(charge_a.id) is None

    # Tenant B records repayment in Tenant B
    repay_b = udhar_b.record_repayment(
        credit_account_id=acc_b.id,
        amount=Decimal("500.00"),
        description="Tenant B Repayment",
    )

    # Tenant B cannot allocate repayment to Tenant A's charge
    with pytest.raises(NotFoundError):
        udhar_b.allocate_repayment(
            repayment_transaction_id=repay_b.id,
            charge_transaction_id=charge_a.id,
            amount=Decimal("500.00"),
        )


def test_cross_tenant_inventory_movement_isolation(db_session: Session, tenants: dict):
    """Verify inventory movements cannot be recorded against another tenant's products."""
    ctx_b = tenants["tenant_b"]["context"]
    prod_a = tenants["tenant_a"]["product"]

    inv_repo_b = InventoryRepository(db_session, ctx_b)

    # Tenant B attempting to create an inventory movement for Tenant A's product is blocked
    with pytest.raises(NotFoundError):
        inv_repo_b.record_movement(
            product_id=prod_a.id,
            movement_type="PURCHASE_RECEIPT",
            quantity=Decimal("10.000"),
        )


@pytest.mark.asyncio
async def test_server_side_business_membership_enforcement(db_session: Session, tenants: dict):
    """Verify that get_business_context strictly checks business membership."""
    user_b = tenants["tenant_b"]["user"]
    business_a = tenants["tenant_a"]["business"]
    business_b = tenants["tenant_b"]["business"]

    # 1. User B successfully resolves context for their own business
    context = await get_business_context(
        current_user=user_b,
        x_business_id=business_b.id,
        db=db_session,
    )
    assert context.business_id == business_b.id
    assert context.role == "owner"

    # 2. User B claiming business A via header is rejected with ForbiddenError
    with pytest.raises(ForbiddenError):
        await get_business_context(
            current_user=user_b,
            x_business_id=business_a.id,
            db=db_session,
        )
