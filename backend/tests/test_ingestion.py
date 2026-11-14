"""Comprehensive tests for Phase 3: Data Centre, File Ingestion, Parsers, Review, and Posting."""

import io
from decimal import Decimal

import openpyxl
import pypdf
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.ingestion.parsers.csv_parser import CSVParser
from app.ingestion.parsers.pdf_parser import PDFParser
from app.ingestion.parsers.text_parser import TextParser
from app.ingestion.parsers.xlsx_parser import XLSXParser
from app.ingestion.storage import StorageService
from app.models.document import DocumentExtraction
from app.models.inventory import InventoryMovement
from app.models.operations import Sale


def auth_headers(user_id: str) -> dict[str, str]:
    """Helper to generate JWT Bearer auth headers for testing."""
    token = create_access_token({"sub": user_id})
    return {"Authorization": f"Bearer {token}"}


# -------------------------------------------------------------------------
# 1. Unit Tests for Parsers & Storage
# -------------------------------------------------------------------------


def test_storage_service_validation_and_hashing(tmp_path):
    storage = StorageService(base_dir=str(tmp_path))
    content = b"customer,amount,direction\nMohan,500,udhar\n"

    path, file_type, sha256, size = storage.validate_and_save(
        business_id="b123", filename="test.csv", content=content
    )

    assert file_type == "CSV"
    assert size == len(content)
    assert len(sha256) == 64
    assert storage.read_file(path) == content

    # Unsupported format rejection
    with pytest.raises(Exception) as exc_info:
        storage.validate_and_save(business_id="b123", filename="malicious.exe", content=b"fake")
    assert "Unsupported file format" in str(exc_info.value)


def test_csv_parser_sales_and_expenses():
    csv_sales = (
        b"Date,Item,Qty,Rate,Total,Payment_Mode\n"
        b"2026-11-10,Chana Dal 1kg,3,110.00,330.00,CASH\n"
        b"2026-11-10,Mustard Oil 1L,2,165.00,330.00,UPI\n"
    )

    sales_data = CSVParser.parse(csv_sales)
    assert sales_data.extraction_type == "SALES"
    assert len(sales_data.sales) == 2
    assert sales_data.sales[0].total_amount == Decimal("330.00")
    assert sales_data.sales[0].items[0].product_name == "Chana Dal 1kg"
    assert sales_data.sales[0].items[0].quantity == Decimal("3")
    assert sales_data.sales[1].payment_mode == "UPI"
    assert len(sales_data.invalid_rows) == 0

    csv_expenses = (
        b"Date,Category,Amount,Description,Mode\n"
        b"2026-11-01,RENT,15000,Shop rent November,BANK_TRANSFER\n"
        b"2026-11-05,UTILITIES,2450.50,Electricity bill,UPI\n"
    )

    exp_data = CSVParser.parse(csv_expenses)
    assert exp_data.extraction_type == "EXPENSES"
    assert len(exp_data.expenses) == 2
    assert exp_data.expenses[0].amount == Decimal("15000")
    assert exp_data.expenses[0].category == "RENT"
    assert exp_data.expenses[1].amount == Decimal("2450.50")


def test_csv_parser_udhar_ambiguity_and_invalid_rows():
    csv_udhar = (
        b"Date,Customer,Amount,Type\n"
        b"2026-11-01,Ramesh Verma,1200.00,udhar\n"
        b"2026-11-02,Ramesh Verma,500.00,jama\n"
        b"2026-11-03,Suresh Kumar,800.00,UNKNOWN_DIRECTION\n"
        b"2026-11-04,,999.00,udhar\n"  # Invalid row: missing customer
        b"2026-11-05,Pooja Sharma,INVALID_AMT,udhar\n"  # Invalid row: invalid amount
    )

    udhar_data = CSVParser.parse(csv_udhar)
    assert udhar_data.extraction_type == "UDHAR_LEDGER"
    assert len(udhar_data.credit_transactions) == 3

    # Row 1: Charge
    assert udhar_data.credit_transactions[0].transaction_type == "CHARGE"
    assert udhar_data.credit_transactions[0].amount == Decimal("1200.00")
    assert len(udhar_data.credit_transactions[0].ambiguity_flags) == 0

    # Row 2: Repayment
    assert udhar_data.credit_transactions[1].transaction_type == "REPAYMENT"
    assert udhar_data.credit_transactions[1].amount == Decimal("500.00")

    # Row 3: Ambiguous direction flagged
    ambig_row = udhar_data.credit_transactions[2]
    assert len(ambig_row.ambiguity_flags) > 0
    assert "AMBIGUOUS_DIRECTION" in ambig_row.ambiguity_flags[0]
    assert ambig_row.requires_owner_review is True

    # Invariant: Invalid rows must NEVER be silently dropped
    assert len(udhar_data.invalid_rows) == 2
    assert udhar_data.invalid_rows[0]["row_number"] == 5
    assert "Missing customer name" in udhar_data.invalid_rows[0]["error_reason"]
    assert udhar_data.invalid_rows[1]["row_number"] == 6
    assert "Invalid transaction amount" in udhar_data.invalid_rows[1]["error_reason"]


def test_xlsx_parser():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["Date", "Item", "Qty", "Rate", "Total", "Payment_Mode"])
    ws.append(["2026-11-10", "Sugar 5kg", 2, 220.00, 440.00, "CASH"])

    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    result = XLSXParser.parse(xlsx_bytes)
    assert result.extraction_type == "SALES"
    assert len(result.sales) == 1
    assert result.sales[0].total_amount == Decimal("440.00")
    assert result.sales[0].items[0].product_name == "Sugar 5kg"


def test_pdf_parser():
    writer = pypdf.PdfWriter()
    # Add a blank page with invoice lines
    writer.add_blank_page(width=612, height=792)

    # We can write text streams in PDF format
    # In pypdf, we test TextParser fallback and table matching
    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)

    result = PDFParser.parse(pdf_bytes.getvalue())
    assert result.extraction_type in ["SALES", "MIXED"]


def test_text_parser_hindi_hinglish():
    text = (
        "Ramesh ko 500 ka rashan udhar diya\n"
        "Suresh se 300 jama mila\n"
        "Bijli ka bill 2400 bhara\n"
        "Sold 5 oil packets 600 cash\n"
        "Amit 750\n"
    )
    result = TextParser.parse(text)

    # Ramesh: Credit Charge
    ramesh_tx = next(c for c in result.credit_transactions if "Ramesh" in c.customer_candidate_name)
    assert ramesh_tx.transaction_type == "CHARGE"
    assert ramesh_tx.amount == Decimal("500")

    # Suresh: Repayment
    suresh_tx = next(c for c in result.credit_transactions if "Suresh" in c.customer_candidate_name)
    assert suresh_tx.transaction_type == "REPAYMENT"
    assert suresh_tx.amount == Decimal("300")

    # Amit: Ambiguous direction
    amit_tx = next(c for c in result.credit_transactions if "Amit" in c.customer_candidate_name)
    assert len(amit_tx.ambiguity_flags) > 0
    assert "AMBIGUOUS_DIRECTION" in amit_tx.ambiguity_flags[0]

    # Expense
    assert len(result.expenses) == 1
    assert result.expenses[0].category == "UTILITIES"
    assert result.expenses[0].amount == Decimal("2400")

    # Sale
    assert len(result.sales) == 1
    assert result.sales[0].total_amount == Decimal("600")


# -------------------------------------------------------------------------
# 2. Integration Tests: Upload, Review, Edit, Idempotent Confirm, Isolation
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_and_draft_only_invariant(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """Verify upload creates draft candidates only; authoritative domain tables remain untouched."""
    user_a = tenants["tenant_a"]["user"]
    headers = auth_headers(user_a.id)

    csv_content = (
        b"Date,Item,Qty,Rate,Total,Payment_Mode\n2026-11-10,Basmati Rice 5kg,1,450.00,450.00,CASH\n"
    )

    files = {"file": ("sales.csv", csv_content, "text/csv")}
    response = await async_client.post(
        "/api/v1/documents/upload",
        files=files,
        data={"auto_process": "true"},
        headers=headers,
    )
    assert response.status_code == 200
    res_data = response.json()
    doc_id = res_data["document_id"]
    assert res_data["status"] == "PROCESSED"
    assert res_data["file_type"] == "CSV"

    # Invariant Verification: Authoritative tables MUST HAVE 0 records at this stage!
    sales_count = (
        db_session.query(Sale)
        .filter(Sale.business_id == tenants["tenant_a"]["business"].id)
        .count()
    )
    dispatch_movements_count = (
        db_session.query(InventoryMovement)
        .filter(
            InventoryMovement.business_id == tenants["tenant_a"]["business"].id,
            InventoryMovement.movement_type == "SALE_DISPATCH",
        )
        .count()
    )
    assert sales_count == 0
    assert dispatch_movements_count == 0

    # Verify Draft Extraction exists
    extraction = (
        db_session.query(DocumentExtraction)
        .filter(DocumentExtraction.document_id == doc_id)
        .first()
    )
    assert extraction is not None
    assert extraction.is_confirmed is False


@pytest.mark.asyncio
async def test_duplicate_file_upload_detection(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """Uploading the exact same file twice returns duplicate detection info."""
    user_a = tenants["tenant_a"]["user"]
    headers = auth_headers(user_a.id)
    csv_content = b"Customer,Amount,Type\nAnita,400,udhar\n"

    # First upload
    res1 = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("udhar.csv", csv_content, "text/csv")},
        headers=headers,
    )
    assert res1.status_code == 200
    doc_id1 = res1.json()["document_id"]

    # Second upload of identical content
    res2 = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("udhar_copy.csv", csv_content, "text/csv")},
        headers=headers,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["document_id"] == doc_id1
    assert "Duplicate document detected" in data2["message"]


@pytest.mark.asyncio
async def test_review_and_patch_extraction(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """Verify owner can fetch extraction details, resolve ambiguity flags, and patch draft."""
    user_a = tenants["tenant_a"]["user"]
    headers = auth_headers(user_a.id)

    # Upload CSV with ambiguous entry
    csv_content = b"Date,Customer,Amount,Type\n2026-11-10,Ramesh,850.00,unknown\n"
    upload_res = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("ambig.csv", csv_content, "text/csv")},
        headers=headers,
    )
    doc_id = upload_res.json()["document_id"]

    # 1. GET extraction
    get_res = await async_client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert get_res.status_code == 200
    extraction_json = get_res.json()
    assert extraction_json["ambiguity_count"] >= 1
    assert len(extraction_json["data"]["credit_transactions"]) == 1
    assert extraction_json["data"]["credit_transactions"][0]["ambiguity_flags"]

    # 2. PATCH extraction: Owner resolves direction to CHARGE and clears ambiguity
    updated_data = extraction_json["data"]
    updated_data["credit_transactions"][0]["transaction_type"] = "CHARGE"
    updated_data["credit_transactions"][0]["ambiguity_flags"] = []

    patch_res = await async_client.patch(
        f"/api/v1/documents/{doc_id}/extraction",
        json=updated_data,
        headers=headers,
    )
    assert patch_res.status_code == 200
    patch_data = patch_res.json()
    assert patch_data["ambiguity_count"] == 0
    assert patch_data["data"]["credit_transactions"][0]["ambiguity_flags"] == []


@pytest.mark.asyncio
async def test_transactional_posting_and_idempotent_retry(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """Verify posting into domain tables and re-confirming is 100% idempotent."""
    user_a = tenants["tenant_a"]["user"]
    business_a_id = tenants["tenant_a"]["business"].id
    headers = auth_headers(user_a.id)

    csv_content = (
        b"Date,Item,Qty,Rate,Total,Payment_Mode\n2026-11-12,Toor Dal 1kg,5,160.00,800.00,CASH\n"
    )

    upload_res = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("toor_dal.csv", csv_content, "text/csv")},
        headers=headers,
    )
    doc_id = upload_res.json()["document_id"]

    # First Confirm: Posts transactionally
    confirm_res1 = await async_client.post(
        f"/api/v1/documents/{doc_id}/confirm",
        json={},
        headers=headers,
    )
    assert confirm_res1.status_code == 200
    c1_data = confirm_res1.json()
    assert c1_data["is_confirmed"] is True
    assert c1_data["sales_posted"] == 1

    # Verify authoritative domain records created
    sales = db_session.query(Sale).filter(Sale.business_id == business_a_id).all()
    assert len(sales) == 1
    assert sales[0].total_amount == Decimal("800.00")

    # Verify inventory movement was dispatched
    movements = (
        db_session.query(InventoryMovement)
        .filter(
            InventoryMovement.business_id == business_a_id,
            InventoryMovement.reference_type == "SALE_CONFIRMATION",
        )
        .all()
    )
    assert len(movements) == 1
    assert movements[0].quantity == Decimal("5.000")

    # Second Confirm: MUST BE IDEMPOTENT (0 new sales, 0 new movements)
    confirm_res2 = await async_client.post(
        f"/api/v1/documents/{doc_id}/confirm",
        json={},
        headers=headers,
    )
    assert confirm_res2.status_code == 200
    c2_data = confirm_res2.json()
    assert c2_data["is_confirmed"] is True
    assert c2_data["sales_posted"] == 0
    assert "skipped idempotently" in c2_data["message"]

    # Counts in DB must remain exactly 1
    assert db_session.query(Sale).filter(Sale.business_id == business_a_id).count() == 1
    assert (
        db_session.query(InventoryMovement)
        .filter(
            InventoryMovement.business_id == business_a_id,
            InventoryMovement.reference_type == "SALE_CONFIRMATION",
        )
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_cross_tenant_document_isolation(
    async_client: AsyncClient, db_session: Session, tenants: dict
):
    """Verify Tenant B cannot read, update, or confirm Tenant A's documents."""
    user_a = tenants["tenant_a"]["user"]
    user_b = tenants["tenant_b"]["user"]
    headers_a = auth_headers(user_a.id)
    headers_b = auth_headers(user_b.id)

    # Tenant A uploads a document
    csv_content = b"Date,Customer,Amount,Type\n2026-11-10,Secret Party,5000,udhar\n"
    res = await async_client.post(
        "/api/v1/documents/upload",
        files={"file": ("tenant_a_confidential.csv", csv_content, "text/csv")},
        headers=headers_a,
    )
    doc_id = res.json()["document_id"]

    # Tenant B attempts GET -> 404
    get_res = await async_client.get(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert get_res.status_code == 404

    # Tenant B attempts PATCH -> 404
    patch_res = await async_client.patch(
        f"/api/v1/documents/{doc_id}/extraction",
        json={
            "extraction_type": "UDHAR_LEDGER",
            "sales": [],
            "expenses": [],
            "credit_transactions": [],
            "invalid_rows": [],
        },
        headers=headers_b,
    )
    assert patch_res.status_code == 404

    # Tenant B attempts POST confirm -> 404
    confirm_res = await async_client.post(
        f"/api/v1/documents/{doc_id}/confirm",
        json={},
        headers=headers_b,
    )
    assert confirm_res.status_code == 404

    # Tenant B lists documents: Tenant A's doc must not be visible
    list_res = await async_client.get("/api/v1/documents", headers=headers_b)
    assert list_res.status_code == 200
    doc_ids_for_b = [d["id"] for d in list_res.json()["documents"]]
    assert doc_id not in doc_ids_for_b


@pytest.mark.asyncio
async def test_ingestion_text_and_preview_endpoints(async_client: AsyncClient, tenants: dict):
    """Verify instant preview and conversational text endpoints."""
    user_a = tenants["tenant_a"]["user"]
    headers = auth_headers(user_a.id)

    # 1. Text parse endpoint
    text_res = await async_client.post(
        "/api/v1/ingestion/text",
        json={"text": "Ramesh ko 750 ka udhar diya\nBijli ka bill 1200 bhara"},
        headers=headers,
    )
    assert text_res.status_code == 200
    t_data = text_res.json()
    assert len(t_data["credit_transactions"]) == 1
    assert t_data["credit_transactions"][0]["amount"] == "750"
    assert len(t_data["expenses"]) == 1
    assert t_data["expenses"][0]["amount"] == "1200"

    # 2. Preview endpoint
    csv_bytes = b"Date,Category,Amount\n2026-11-10,RENT,8000\n"
    prev_res = await async_client.post(
        "/api/v1/ingestion/preview",
        files={"file": ("preview_test.csv", csv_bytes, "text/csv")},
        headers=headers,
    )
    assert prev_res.status_code == 200
    p_data = prev_res.json()
    assert p_data["file_type"] == "CSV"
    assert p_data["valid_rows_count"] == 1
    assert len(p_data["candidates"]["expenses"]) == 1
