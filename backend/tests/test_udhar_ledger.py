"""Tests for Udhar Ledger financial event model, allocations, and invariants."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError
from app.models.udhar import TransactionStatus, TransactionType
from app.repositories.udhar import UdharRepository


def test_udhar_charges_repayments_and_derived_balance(db_session: Session, tenants: dict):
    """Verify charges increase receivables, repayments reduce them, and balance is derived."""
    ctx_a = tenants["tenant_a"]["context"]
    acc_a = tenants["tenant_a"]["credit_account"]

    udhar = UdharRepository(db_session, ctx_a)

    # Initial balance is 0.00
    assert udhar.get_account_balance(acc_a.id) == Decimal("0.00")

    # 1. First charge: ₹1,500.00
    c1 = udhar.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("1500.00"),
        description="Kirana groceries on credit",
        reference="BILL-101",
    )
    assert c1.transaction_type == TransactionType.CHARGE.value
    assert udhar.get_account_balance(acc_a.id) == Decimal("1500.00")

    # 2. Second charge: ₹750.50
    udhar.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("750.50"),
        description="Rice & spices credit",
        reference="BILL-102",
    )
    assert udhar.get_account_balance(acc_a.id) == Decimal("2250.50")

    # 3. Partial repayment: ₹1,000.00 (reduces outstanding)
    r1 = udhar.record_repayment(
        credit_account_id=acc_a.id,
        amount=Decimal("1000.00"),
        description="UPI repayment by customer",
        reference="UPI-REF-001",
    )
    assert r1.transaction_type == TransactionType.REPAYMENT.value
    assert udhar.get_account_balance(acc_a.id) == Decimal("1250.50")


def test_repayment_allocation_invariants(db_session: Session, tenants: dict):
    """Verify repayment allocations cannot exceed repayment amount or open charge balance."""
    ctx_a = tenants["tenant_a"]["context"]
    acc_a = tenants["tenant_a"]["credit_account"]

    udhar = UdharRepository(db_session, ctx_a)

    # Charge: ₹1,000.00
    charge = udhar.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("1000.00"),
    )

    # Repayment: ₹600.00
    repay = udhar.record_repayment(
        credit_account_id=acc_a.id,
        amount=Decimal("600.00"),
    )

    # 1. Partial allocation: ₹400.00 -> succeeds
    alloc1 = udhar.allocate_repayment(
        repayment_transaction_id=repay.id,
        charge_transaction_id=charge.id,
        amount=Decimal("400.00"),
    )
    assert alloc1.allocated_amount == Decimal("400.00")

    # 2. Attempting to allocate another ₹300.00 (total ₹700 > repayment ₹600) -> must fail
    with pytest.raises(BadRequestError) as exc_info:
        udhar.allocate_repayment(
            repayment_transaction_id=repay.id,
            charge_transaction_id=charge.id,
            amount=Decimal("300.00"),
        )
    assert "exceeds available repayment amount" in str(exc_info.value)

    # 3. Allocate remaining ₹200.00 -> succeeds (repayment fully allocated: ₹600)
    alloc2 = udhar.allocate_repayment(
        repayment_transaction_id=repay.id,
        charge_transaction_id=charge.id,
        amount=Decimal("200.00"),
    )
    assert alloc2.allocated_amount == Decimal("200.00")

    # 4. New repayment of ₹800.00
    repay2 = udhar.record_repayment(
        credit_account_id=acc_a.id,
        amount=Decimal("800.00"),
    )

    # Charge only has ₹400 remaining open (1000 - 600 allocated = 400).
    # Attempting to allocate ₹500 to it must fail!
    with pytest.raises(BadRequestError) as exc_info:
        udhar.allocate_repayment(
            repayment_transaction_id=repay2.id,
            charge_transaction_id=charge.id,
            amount=Decimal("500.00"),
        )
    assert "exceeds open charge amount" in str(exc_info.value)

    # Allocating exact open balance ₹400 -> succeeds
    alloc3 = udhar.allocate_repayment(
        repayment_transaction_id=repay2.id,
        charge_transaction_id=charge.id,
        amount=Decimal("400.00"),
    )
    assert alloc3.allocated_amount == Decimal("400.00")


def test_udhar_idempotency_prevents_duplicate_postings(db_session: Session, tenants: dict):
    """Verify idempotency key prevents duplicate transactions on network retry."""
    ctx_a = tenants["tenant_a"]["context"]
    acc_a = tenants["tenant_a"]["credit_account"]

    udhar = UdharRepository(db_session, ctx_a)

    idemp_key = "idemp_charge_req_998877"

    # First call
    tx1 = udhar.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("500.00"),
        idempotency_key=idemp_key,
    )

    # Second call with identical key
    tx2 = udhar.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("500.00"),
        idempotency_key=idemp_key,
    )

    assert tx1.id == tx2.id
    # Balance must only be ₹500, not ₹1000
    assert udhar.get_account_balance(acc_a.id) == Decimal("500.00")


def test_udhar_reversal_compensating_workflow(db_session: Session, tenants: dict):
    """Verify that mistakes are resolved through compensating reversal entries."""
    ctx_a = tenants["tenant_a"]["context"]
    acc_a = tenants["tenant_a"]["credit_account"]

    udhar = UdharRepository(db_session, ctx_a)

    # Erroneous charge of ₹800.00
    orig_tx = udhar.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("800.00"),
        description="Erroneous charge",
    )
    assert udhar.get_account_balance(acc_a.id) == Decimal("800.00")

    # Reverse transaction
    reversal = udhar.record_reversal(
        original_transaction_id=orig_tx.id,
        reason="Customer returned bill before taking delivery",
    )

    assert reversal.transaction_type == TransactionType.REVERSAL.value
    assert reversal.reverses_transaction_id == orig_tx.id
    assert orig_tx.status == TransactionStatus.REVERSED.value

    # Derived balance drops back to ₹0.00
    assert udhar.get_account_balance(acc_a.id) == Decimal("0.00")

    # Attempting to reverse an already reversed transaction is rejected
    with pytest.raises(ConflictError):
        udhar.record_reversal(orig_tx.id, "Attempt duplicate reversal")


def test_positive_amounts_strictly_enforced(db_session: Session, tenants: dict):
    """Verify zero or negative ledger amounts are rejected."""
    ctx_a = tenants["tenant_a"]["context"]
    acc_a = tenants["tenant_a"]["credit_account"]

    udhar = UdharRepository(db_session, ctx_a)

    with pytest.raises(BadRequestError):
        udhar.record_charge(acc_a.id, Decimal("0.00"))

    with pytest.raises(BadRequestError):
        udhar.record_charge(acc_a.id, Decimal("-150.00"))

    with pytest.raises(BadRequestError):
        udhar.record_repayment(acc_a.id, Decimal("-50.00"))
