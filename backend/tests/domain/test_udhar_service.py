"""Hand-checked tests for UdharService aging calculations and statement reconciliation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.udhar.service import UdharService
from app.repositories.udhar import UdharRepository


def test_udhar_aging_buckets_hand_checked(db_session: Session, tenants: dict):
    """Verify overdue aging bucket classification and allocation subtraction."""
    ctx_a = tenants["tenant_a"]["context"]
    acc_a = tenants["tenant_a"]["credit_account"]

    udhar_repo = UdharRepository(db_session, ctx_a)
    service = UdharService(db_session, ctx_a)

    fixed_now = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)

    # Charge 1: Due in 5 days -> NOT_DUE (₹500.00)
    udhar_repo.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("500.00"),
        due_at=fixed_now + timedelta(days=5),
        description="Current bill",
    )

    # Charge 2: Due 4 days ago -> 1_7_DAYS (₹1000.00)
    udhar_repo.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("1000.00"),
        due_at=fixed_now - timedelta(days=4),
        description="4 days overdue",
    )

    # Charge 3: Due 20 days ago -> 8_30_DAYS (₹2000.00)
    c3 = udhar_repo.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("2000.00"),
        due_at=fixed_now - timedelta(days=20),
        description="20 days overdue",
    )

    # Charge 4: Due 45 days ago -> 31_60_DAYS (₹3000.00)
    udhar_repo.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("3000.00"),
        due_at=fixed_now - timedelta(days=45),
        description="45 days overdue",
    )

    # Charge 5: Due 90 days ago -> 60_PLUS_DAYS (₹4000.00)
    udhar_repo.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("4000.00"),
        due_at=fixed_now - timedelta(days=90),
        description="90 days overdue",
    )

    # Partial repayment of ₹500 allocated to Charge 3 (reducing open balance to ₹1500)
    repay = udhar_repo.record_repayment(
        credit_account_id=acc_a.id,
        amount=Decimal("500.00"),
    )
    udhar_repo.allocate_repayment(
        repayment_transaction_id=repay.id,
        charge_transaction_id=c3.id,
        amount=Decimal("500.00"),
    )

    summary_result = service.get_udhar_summary(as_of_date=fixed_now)
    summary = summary_result.data

    # Total receivables = 500 + 1000 + (2000 - 500) + 3000 + 4000 = 10,000.00
    assert summary.total_receivables == Decimal("10000.00")

    # Overdue = 1000 + 1500 + 3000 + 4000 = 9,500.00
    assert summary.overdue_amount == Decimal("9500.00")

    bucket_map = {b.bucket_key: b.amount for b in summary.aging_buckets}
    assert bucket_map["NOT_DUE"] == Decimal("500.00")
    assert bucket_map["1_7_DAYS"] == Decimal("1000.00")
    assert bucket_map["8_30_DAYS"] == Decimal("1500.00")  # 2000 - 500 allocated!
    assert bucket_map["31_60_DAYS"] == Decimal("3000.00")
    assert bucket_map["60_PLUS_DAYS"] == Decimal("4000.00")


def test_customer_statement_reconciles_to_ledger(db_session: Session, tenants: dict):
    """Verify statement line items, running balance, and closing reconciliation."""
    ctx_a = tenants["tenant_a"]["context"]
    cust_a = tenants["tenant_a"]["customer"]
    acc_a = tenants["tenant_a"]["credit_account"]

    udhar_repo = UdharRepository(db_session, ctx_a)
    service = UdharService(db_session, ctx_a)

    # 1. Charge ₹1200.00
    udhar_repo.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("1200.00"),
        description="Grocery items",
    )

    # 2. Charge ₹800.00
    udhar_repo.record_charge(
        credit_account_id=acc_a.id,
        amount=Decimal("800.00"),
        description="Milk & ghee",
    )

    # 3. Repayment ₹500.00
    udhar_repo.record_repayment(
        credit_account_id=acc_a.id,
        amount=Decimal("500.00"),
        description="Cash payment",
    )

    stmt_result = service.generate_statement(cust_a.id)
    stmt = stmt_result.data

    assert stmt.opening_balance == Decimal("0.00")
    assert stmt.total_charges == Decimal("2000.00")
    assert stmt.total_repayments == Decimal("500.00")
    assert stmt.closing_balance == Decimal("1500.00")

    # Invariant: Must equal authoritative repo balance
    assert stmt.closing_balance == udhar_repo.get_account_balance(acc_a.id)

    # Verify line items
    assert len(stmt.lines) == 3
    assert stmt.lines[0].running_balance == Decimal("1200.00")
    assert stmt.lines[1].running_balance == Decimal("2000.00")
    assert stmt.lines[2].running_balance == Decimal("1500.00")
