"""Comprehensive integration tests for Udhar Management API, Ledger, and Invariants."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.security import create_access_token


def _auth_headers(user_id: str) -> dict[str, str]:
    """Helper to obtain JWT Bearer auth headers for testing."""
    token = create_access_token({"sub": user_id})
    return {"Authorization": f"Bearer {token}"}


def test_udhar_summary_endpoint(client: TestClient, tenants: dict):
    """Verify store-wide udhar summary endpoint returns valid metrics and aging buckets."""
    user_a = tenants["tenant_a"]["user"]
    headers = _auth_headers(user_a.id)
    resp = client.get("/api/v1/udhar/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "evidence" in data
    summary = data["data"]
    assert "total_receivables" in summary
    assert "overdue_amount" in summary
    assert "aging_buckets" in summary
    assert len(summary["aging_buckets"]) == 5
    bucket_keys = [b["bucket_key"] for b in summary["aging_buckets"]]
    assert "NOT_DUE" in bucket_keys
    assert "1_7_DAYS" in bucket_keys
    assert "8_30_DAYS" in bucket_keys
    assert "31_60_DAYS" in bucket_keys
    assert "60_PLUS_DAYS" in bucket_keys


def test_customer_crud_duplicate_detection_and_archiving(client: TestClient, tenants: dict):
    """Verify customer creation, duplicate warnings, updating, and soft-archiving."""
    user_a = tenants["tenant_a"]["user"]
    headers = _auth_headers(user_a.id)

    # 1. Create initial customer
    create_payload = {
        "display_name": "Ramesh Kumar Sharma",
        "phone_e164": "+919876543210",
        "notes": "Regular kirana customer",
        "credit_limit": "5000.00",
    }
    resp1 = client.post("/api/v1/udhar/customers", json=create_payload, headers=headers)
    assert resp1.status_code == 201
    res1_data = resp1.json()
    cust1 = res1_data["customer"]
    assert cust1["display_name"] == "Ramesh Kumar Sharma"
    assert cust1["phone_e164"] == "+919876543210"
    assert cust1["credit_limit"] == "5000.00"
    assert cust1["is_active"] is True
    assert res1_data["warnings"] == []

    # 2. Attempt duplicate creation with same phone number
    dup_payload = {
        "display_name": "Ramesh Sharma",
        "phone_e164": "+919876543210",
    }
    resp2 = client.post("/api/v1/udhar/customers", json=dup_payload, headers=headers)
    assert resp2.status_code == 201
    res2_data = resp2.json()
    assert len(res2_data["warnings"]) > 0
    assert len(res2_data["duplicate_matches"]) > 0
    assert res2_data["duplicate_matches"][0]["match_type"] == "PHONE_MATCH"

    # 3. Search customers
    search_resp = client.get("/api/v1/udhar/customers?query=Ramesh", headers=headers)
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) >= 2

    # 4. Update customer
    cust_id = cust1["id"]
    update_payload = {
        "display_name": "Ramesh K. Sharma",
        "credit_limit": "7500.00",
        "reminder_consent_status": "CONSENTED",
    }
    up_resp = client.put(f"/api/v1/udhar/customers/{cust_id}", json=update_payload, headers=headers)
    assert up_resp.status_code == 200
    updated = up_resp.json()
    assert updated["display_name"] == "Ramesh K. Sharma"
    assert updated["credit_limit"] == "7500.00"
    assert updated["reminder_consent_status"] == "CONSENTED"

    # 5. Archive customer
    arch_resp = client.post(f"/api/v1/udhar/customers/{cust_id}/archive", headers=headers)
    assert arch_resp.status_code == 200
    assert arch_resp.json()["is_active"] is False

    # Listed active customers should exclude archived by default
    active_resp = client.get("/api/v1/udhar/customers?query=Ramesh", headers=headers)
    active_ids = [c["id"] for c in active_resp.json()]
    assert cust_id not in active_ids

    # Including archived returns customer
    all_resp = client.get(
        "/api/v1/udhar/customers?query=Ramesh&include_archived=true", headers=headers
    )
    all_ids = [c["id"] for c in all_resp.json()]
    assert cust_id in all_ids

    # 6. Unarchive / Restore customer
    unarch_resp = client.post(f"/api/v1/udhar/customers/{cust_id}/unarchive", headers=headers)
    assert unarch_resp.status_code == 200
    assert unarch_resp.json()["is_active"] is True


def test_customer_opening_balance(client: TestClient, tenants: dict):
    """Verify owner-confirmed opening balance initializes customer balance and ledger entry."""
    headers = _auth_headers(tenants["tenant_a"]["user"].id)

    payload = {
        "display_name": "Sita Ram",
        "phone_e164": "+919811223344",
        "opening_balance": "2500.00",
        "opening_balance_notes": "Brought forward from old paper khata",
    }
    resp = client.post("/api/v1/udhar/customers", json=payload, headers=headers)
    assert resp.status_code == 201
    cust = resp.json()["customer"]
    assert cust["outstanding_balance"] == "2500.00"
    cust_id = cust["id"]

    # Verify ledger shows opening balance
    ledger_resp = client.get(f"/api/v1/udhar/customers/{cust_id}/ledger", headers=headers)
    assert ledger_resp.status_code == 200
    ledger = ledger_resp.json()
    assert ledger["outstanding_balance"] == "2500.00"
    assert len(ledger["lines"]) == 1
    assert ledger["lines"][0]["transaction_type"] == "OPENING_BALANCE"
    assert ledger["lines"][0]["charge_amount"] == "2500.00"
    assert ledger["lines"][0]["running_balance"] == "2500.00"


def test_charge_credit_limit_warning(client: TestClient, tenants: dict):
    """Verify charge increases balance and triggers warning when credit limit is exceeded."""
    headers = _auth_headers(tenants["tenant_a"]["user"].id)

    # Create customer with credit limit ₹3,000.00
    c_resp = client.post(
        "/api/v1/udhar/customers",
        json={"display_name": "Mohan Lal", "credit_limit": "3000.00"},
        headers=headers,
    )
    cust_id = c_resp.json()["customer"]["id"]

    # Charge 1: ₹2,000.00 (within limit)
    ch1_resp = client.post(
        "/api/v1/udhar/charges",
        json={"customer_id": cust_id, "amount": "2000.00", "description": "Wheat flour & Dal"},
        headers=headers,
    )
    assert ch1_resp.status_code == 201
    ch1 = ch1_resp.json()
    assert ch1["new_balance"] == "2000.00"
    assert ch1["credit_limit_warning"] is None

    # Charge 2: ₹1,500.00 (Total ₹3,500 > ₹3,000 limit -> warning emitted)
    ch2_resp = client.post(
        "/api/v1/udhar/charges",
        json={"customer_id": cust_id, "amount": "1500.00", "description": "Spices & Mustard oil"},
        headers=headers,
    )
    assert ch2_resp.status_code == 201
    ch2 = ch2_resp.json()
    assert ch2["new_balance"] == "3500.00"
    assert ch2["credit_limit_warning"] is not None
    assert "exceeds customer credit limit" in ch2["credit_limit_warning"]


def test_repayment_fifo_auto_allocation(client: TestClient, tenants: dict):
    """Verify customer repayment auto-allocates in FIFO order across open charges."""
    headers = _auth_headers(tenants["tenant_a"]["user"].id)

    # Create customer
    c_resp = client.post(
        "/api/v1/udhar/customers",
        json={"display_name": "Gopal Prasad"},
        headers=headers,
    )
    cust_id = c_resp.json()["customer"]["id"]

    # Charge 1: ₹1,000.00
    ch1 = client.post(
        "/api/v1/udhar/charges",
        json={"customer_id": cust_id, "amount": "1000.00", "reference": "BILL-001"},
        headers=headers,
    ).json()

    # Charge 2: ₹1,500.00
    ch2 = client.post(
        "/api/v1/udhar/charges",
        json={"customer_id": cust_id, "amount": "1500.00", "reference": "BILL-002"},
        headers=headers,
    ).json()

    # Balance is now ₹2,500.00
    # Repayment of ₹1,400.00 with auto_allocate=True
    repay_resp = client.post(
        "/api/v1/udhar/repayments",
        json={
            "customer_id": cust_id,
            "amount": "1400.00",
            "payment_mode": "UPI",
            "reference": "UPI-TXN-777",
            "auto_allocate": True,
        },
        headers=headers,
    )
    assert repay_resp.status_code == 201
    repay = repay_resp.json()
    assert repay["amount"] == "1400.00"
    assert repay["payment_mode"] == "UPI"
    assert repay["allocated_amount"] == "1400.00"
    assert repay["unallocated_amount"] == "0.00"
    # Derived balance drops from ₹2,500 to ₹1,100
    assert repay["new_balance"] == "1100.00"

    # Allocations: ₹1,000 to Charge 1 (fully settled), ₹400 to Charge 2 (₹1,100 open)
    allocs = repay["allocations"]
    assert len(allocs) == 2
    assert allocs[0]["charge_transaction_id"] == ch1["transaction_id"]
    assert allocs[0]["allocated_amount"] == "1000.00"
    assert allocs[1]["charge_transaction_id"] == ch2["transaction_id"]
    assert allocs[1]["allocated_amount"] == "400.00"


def test_reversal_compensating_workflow(client: TestClient, tenants: dict):
    """Verify mistake correction through compensating reversal entries."""
    headers = _auth_headers(tenants["tenant_a"]["user"].id)

    # Create customer
    c_resp = client.post(
        "/api/v1/udhar/customers",
        json={"display_name": "Devendra Singh"},
        headers=headers,
    )
    cust_id = c_resp.json()["customer"]["id"]

    # Charge ₹800.00
    ch = client.post(
        "/api/v1/udhar/charges",
        json={"customer_id": cust_id, "amount": "800.00"},
        headers=headers,
    ).json()
    assert ch["new_balance"] == "800.00"

    # Reverse the charge
    rev_resp = client.post(
        f"/api/v1/udhar/transactions/{ch['transaction_id']}/reverse",
        json={"reason": "Entered against wrong customer"},
        headers=headers,
    )
    assert rev_resp.status_code == 200
    rev = rev_resp.json()
    assert rev["original_transaction_id"] == ch["transaction_id"]
    assert rev["amount"] == "800.00"
    assert rev["new_balance"] == "0.00"

    # Attempting to reverse an already reversed transaction is rejected
    dup_rev = client.post(
        f"/api/v1/udhar/transactions/{ch['transaction_id']}/reverse",
        json={"reason": "Attempt duplicate reversal"},
        headers=headers,
    )
    assert dup_rev.status_code == 409


def test_customer_statement_exact_reconciliation(client: TestClient, tenants: dict):
    """Verify statement mathematically reconciles: closing = opening + charges - repayments."""
    headers = _auth_headers(tenants["tenant_a"]["user"].id)

    # Create customer with opening balance of ₹1,000.00
    c_resp = client.post(
        "/api/v1/udhar/customers",
        json={"display_name": "Anil Agarwal", "opening_balance": "1000.00"},
        headers=headers,
    )
    cust_id = c_resp.json()["customer"]["id"]

    # Charge: ₹500.00
    client.post(
        "/api/v1/udhar/charges",
        json={"customer_id": cust_id, "amount": "500.00"},
        headers=headers,
    )

    # Repayment: ₹300.00
    client.post(
        "/api/v1/udhar/repayments",
        json={"customer_id": cust_id, "amount": "300.00", "payment_mode": "CASH"},
        headers=headers,
    )

    # Get statement
    stmt_resp = client.get(f"/api/v1/udhar/customers/{cust_id}/statement", headers=headers)
    assert stmt_resp.status_code == 200
    stmt = stmt_resp.json()["data"]

    opening = Decimal(str(stmt["opening_balance"]))
    total_charges = Decimal(str(stmt["total_charges"]))
    total_repayments = Decimal(str(stmt["total_repayments"]))
    closing = Decimal(str(stmt["closing_balance"]))

    # Invariant: closing_balance == opening_balance + total_charges - total_repayments
    assert closing == opening + total_charges - total_repayments
    assert closing == Decimal("1200.00")


def test_reminder_draft_multilingual_preview(client: TestClient, tenants: dict):
    """Verify reminder draft generation across languages with WhatsApp link and disclaimer."""
    headers = _auth_headers(tenants["tenant_a"]["user"].id)

    # Create customer with phone and charge
    c_resp = client.post(
        "/api/v1/udhar/customers",
        json={"display_name": "Pooja Verma", "phone_e164": "+919876543210"},
        headers=headers,
    )
    cust_id = c_resp.json()["customer"]["id"]

    # Record overdue charge
    due_date = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    client.post(
        "/api/v1/udhar/charges",
        json={"customer_id": cust_id, "amount": "1250.00", "due_at": due_date},
        headers=headers,
    )

    # Hinglish draft
    resp_hi = client.post(
        f"/api/v1/udhar/customers/{cust_id}/reminder-draft",
        json={"language": "Hinglish"},
        headers=headers,
    )
    assert resp_hi.status_code == 200
    d_hi = resp_hi.json()
    assert "Namaste Pooja Verma ji" in d_hi["draft_text"]
    assert "1250.00" in d_hi["draft_text"]
    assert d_hi["whatsapp_link"] is not None
    assert "api.whatsapp.com/send" in d_hi["whatsapp_link"]
    assert "919876543210" in d_hi["whatsapp_link"]
    assert "un-sent preview draft" in d_hi["disclaimer"]

    # English draft
    resp_en = client.post(
        f"/api/v1/udhar/customers/{cust_id}/reminder-draft",
        json={"language": "English"},
        headers=headers,
    )
    assert resp_en.status_code == 200
    assert "Dear Pooja Verma" in resp_en.json()["draft_text"]


def test_udhar_idempotency_prevents_duplicate_charge(client: TestClient, tenants: dict):
    """Verify network retry with same idempotency key creates zero duplicate transactions."""
    headers = _auth_headers(tenants["tenant_a"]["user"].id)

    c_resp = client.post(
        "/api/v1/udhar/customers",
        json={"display_name": "Vikram Patel"},
        headers=headers,
    )
    cust_id = c_resp.json()["customer"]["id"]

    idemp_key = "idemp_charge_retry_001"
    payload = {
        "customer_id": cust_id,
        "amount": "999.00",
        "idempotency_key": idemp_key,
    }

    # First attempt
    res1 = client.post("/api/v1/udhar/charges", json=payload, headers=headers).json()

    # Retry attempt
    res2 = client.post("/api/v1/udhar/charges", json=payload, headers=headers).json()

    assert res1["transaction_id"] == res2["transaction_id"]
    assert res2["new_balance"] == "999.00"


def test_cross_tenant_isolation(client: TestClient, tenants: dict):
    """Verify strict tenant isolation: Tenant B cannot access Tenant A's customer or ledger."""
    headers_a = _auth_headers(tenants["tenant_a"]["user"].id)
    headers_b = _auth_headers(tenants["tenant_b"]["user"].id)

    # Tenant A creates customer
    cA = client.post(
        "/api/v1/udhar/customers",
        json={"display_name": "Tenant A Exclusive Customer"},
        headers=headers_a,
    ).json()["customer"]
    cust_a_id = cA["id"]

    # Tenant B attempts to get Tenant A's customer -> 404
    get_b = client.get(f"/api/v1/udhar/customers/{cust_a_id}", headers=headers_b)
    assert get_b.status_code == 404

    # Tenant B attempts to post charge against Tenant A's customer -> 404
    charge_b = client.post(
        "/api/v1/udhar/charges",
        json={"customer_id": cust_a_id, "amount": "500.00"},
        headers=headers_b,
    )
    assert charge_b.status_code == 404
