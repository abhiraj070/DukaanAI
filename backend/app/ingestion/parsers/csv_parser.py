"""CSV document parser with column auto-detection and validation."""

import csv
import io
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.schemas.ingestion import (
    CandidateCreditTransaction,
    CandidateExpense,
    CandidateSale,
    CandidateSaleItem,
    DocumentExtractionData,
)


def clean_currency_str(val: Any) -> Decimal | None:
    """Parse a monetary string (e.g. '₹ 1,500.50' or '1500') to Decimal."""
    if val is None:
        return None
    s = str(val).strip()
    s = re.sub(r"[^\d.-]", "", s)
    if not s or s == "-":
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def parse_flexible_date(val: Any) -> datetime | None:
    """Parse flexible date formats common in Indian businesses."""
    if not val:
        return None
    s = str(val).strip()
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%Y/%m/%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


class CSVParser:
    """Parses tabular CSV files into candidate records with explicit invalid row reporting."""

    @staticmethod
    def parse(content: bytes) -> DocumentExtractionData:
        """Parse raw CSV bytes into typed candidates."""
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)

        if not rows:
            return DocumentExtractionData(extraction_type="MIXED")

        # Find header row
        headers = [h.strip().lower() for h in rows[0]]
        header_map = {h: idx for idx, h in enumerate(headers)}

        # Helper to find column index by synonyms
        def find_col(synonyms: list[str]) -> int | None:
            for syn in synonyms:
                for h, idx in header_map.items():
                    if syn in h:
                        return idx
            return None

        # Detect schema type by headers
        has_customer = find_col(["customer", "grahak", "khatadar", "khata", "party"]) is not None
        has_product = find_col(["product", "item", "saman", "goods", "sku"]) is not None
        has_category = find_col(["category", "expense_type", "kharcha"]) is not None

        sales: list[CandidateSale] = []
        expenses: list[CandidateExpense] = []
        credits: list[CandidateCreditTransaction] = []
        invalid_rows: list[dict[str, Any]] = []

        if has_customer:
            extraction_type = "UDHAR_LEDGER"
        elif has_category and not has_product:
            extraction_type = "EXPENSES"
        else:
            extraction_type = "SALES"

        col_date = find_col(["date", "tarikh", "created", "time"])
        col_amount = find_col(["amount", "total", "rupees", "inr", "paisa", "price", "rate"])
        col_customer = find_col(["customer", "grahak", "khatadar", "name", "party"])
        col_direction = find_col(
            ["type", "direction", "transaction_type", "jama_udhar", "debit_credit"]
        )
        col_due = find_col(["due_date", "due", "last_date"])
        col_item = find_col(["product", "item", "name", "description", "saman"])
        col_qty = find_col(["quantity", "qty", "units", "packet", "kg", "count"])
        col_rate = find_col(["price", "rate", "unit_price"])
        col_mode = find_col(["payment_mode", "mode", "payment", "cash_upi"])
        col_category = find_col(["category", "expense_type", "type"])
        col_desc = find_col(["description", "desc", "notes", "details"])

        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or all(not cell.strip() for cell in row):
                continue  # skip completely empty lines

            try:
                dt = (
                    parse_flexible_date(row[col_date])
                    if col_date is not None and col_date < len(row)
                    else datetime.now(UTC)
                )

                if extraction_type == "UDHAR_LEDGER":
                    cust_name = (
                        row[col_customer].strip()
                        if col_customer is not None and col_customer < len(row)
                        else ""
                    )
                    if not cust_name:
                        raise ValueError("Missing customer name")

                    amt = (
                        clean_currency_str(row[col_amount])
                        if col_amount is not None and col_amount < len(row)
                        else None
                    )
                    if amt is None or amt <= Decimal("0"):
                        raw_val = (
                            row[col_amount]
                            if col_amount is not None and col_amount < len(row)
                            else ""
                        )
                        raise ValueError(f"Invalid transaction amount '{raw_val}'")

                    # Direction detection (CHARGE / DEBIT vs REPAYMENT / CREDIT)
                    dir_str = (
                        row[col_direction].strip().lower()
                        if col_direction is not None and col_direction < len(row)
                        else ""
                    )
                    ambiguity_flags = []

                    if any(
                        w in dir_str for w in ["charge", "debit", "udhar", "diya", "due", "sale"]
                    ):
                        tx_type = "CHARGE"
                    elif any(
                        w in dir_str
                        for w in ["repayment", "credit", "jama", "aaya", "mila", "pay", "paid"]
                    ):
                        tx_type = "REPAYMENT"
                    else:
                        # Ambiguous direction
                        tx_type = "CHARGE"
                        ambiguity_flags.append(
                            "AMBIGUOUS_DIRECTION: Transaction direction unclear from import"
                        )

                    due_date = (
                        parse_flexible_date(row[col_due])
                        if col_due is not None and col_due < len(row)
                        else None
                    )

                    credits.append(
                        CandidateCreditTransaction(
                            customer_candidate_name=cust_name,
                            transaction_type=tx_type,
                            amount=amt,
                            transaction_at=dt,
                            due_at=due_date,
                            source_row=row_idx,
                            confidence=0.95 if not ambiguity_flags else 0.60,
                            ambiguity_flags=ambiguity_flags,
                            requires_owner_review=True,
                        )
                    )

                elif extraction_type == "EXPENSES":
                    amt = (
                        clean_currency_str(row[col_amount])
                        if col_amount is not None and col_amount < len(row)
                        else None
                    )
                    if amt is None or amt <= Decimal("0"):
                        raw_val = (
                            row[col_amount]
                            if col_amount is not None and col_amount < len(row)
                            else ""
                        )
                        raise ValueError(f"Invalid expense amount '{raw_val}'")

                    cat = (
                        row[col_category].strip().upper()
                        if col_category is not None and col_category < len(row)
                        else "OTHER"
                    )
                    desc = (
                        row[col_desc].strip()
                        if col_desc is not None and col_desc < len(row)
                        else None
                    )
                    mode = (
                        row[col_mode].strip().upper()
                        if col_mode is not None and col_mode < len(row)
                        else "CASH"
                    )

                    expenses.append(
                        CandidateExpense(
                            category=cat,
                            amount=amt,
                            expense_date=dt,
                            description=desc,
                            payment_mode=mode,
                            source_row=row_idx,
                            confidence=1.0,
                        )
                    )

                else:  # SALES
                    amt = (
                        clean_currency_str(row[col_amount])
                        if col_amount is not None and col_amount < len(row)
                        else None
                    )
                    item_name = (
                        row[col_item].strip()
                        if col_item is not None and col_item < len(row)
                        else "Item"
                    )
                    qty = (
                        clean_currency_str(row[col_qty])
                        if col_qty is not None and col_qty < len(row)
                        else Decimal("1.000")
                    )
                    rate = (
                        clean_currency_str(row[col_rate])
                        if col_rate is not None and col_rate < len(row)
                        else None
                    )

                    if amt is None and rate is not None and qty is not None:
                        amt = rate * qty
                    elif (
                        amt is not None and rate is None and qty is not None and qty > Decimal("0")
                    ):
                        rate = amt / qty

                    if amt is None or amt <= Decimal("0"):
                        raise ValueError("Invalid total amount")

                    mode = (
                        row[col_mode].strip().upper()
                        if col_mode is not None and col_mode < len(row)
                        else "CASH"
                    )

                    sales.append(
                        CandidateSale(
                            sale_number=f"IMP-R{row_idx}",
                            sold_at=dt,
                            total_amount=amt,
                            payment_mode=mode,
                            source_row=row_idx,
                            confidence=1.0,
                            items=[
                                CandidateSaleItem(
                                    product_name=item_name,
                                    quantity=qty or Decimal("1.000"),
                                    unit_price=rate or amt,
                                    total_amount=amt,
                                    source_row=row_idx,
                                )
                            ],
                        )
                    )

            except Exception as e:
                # Invariant: Never silently drop an invalid row
                invalid_rows.append(
                    {
                        "row_number": row_idx,
                        "raw_data": row,
                        "error_reason": str(e),
                    }
                )

        return DocumentExtractionData(
            extraction_type=extraction_type,
            sales=sales,
            expenses=expenses,
            credit_transactions=credits,
            invalid_rows=invalid_rows,
        )
