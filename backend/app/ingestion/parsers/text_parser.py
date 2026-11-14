"""Natural language text parser supporting English, Hindi, and Hinglish kirana entries."""

import re
from datetime import UTC, datetime
from decimal import Decimal

from app.schemas.ingestion import (
    CandidateCreditTransaction,
    CandidateExpense,
    CandidateSale,
    CandidateSaleItem,
    DocumentExtractionData,
)


def _extract_amount_and_qty(line: str) -> tuple[Decimal | None, Decimal]:
    """Extract money amount and quantity from a text line."""
    line_lower = line.lower()

    # Check for quantity attached to unit: e.g. "5 oil packets", "10 kg", "2 packets"
    qty = Decimal("1.000")
    qty_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:packets?|pkt|bottles?|kg|litres?|l|pcs?|units?|items?|bora)\b",
        line_lower,
    )
    if qty_match:
        try:
            qty = Decimal(qty_match.group(1))
        except Exception:
            pass

    # Find amounts with currency markers or trailing monetary indicator
    # 1. explicit currency prefix: ₹ 500, Rs 500, INR 500
    cur_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)", line_lower)
    if cur_match:
        try:
            return Decimal(cur_match.group(1)), qty
        except Exception:
            pass

    # 2. explicit monetary suffix: 500 rupees, 500 rs, 500 cash, 500 upi, 500 ka
    suffix_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:rupees|rs|cash|upi|ka)\b", line_lower)
    if suffix_match:
        try:
            return Decimal(suffix_match.group(1)), qty
        except Exception:
            pass

    # 3. Fallback: all numbers in line
    all_nums = re.findall(r"\b\d+(?:\.\d+)?\b", line_lower)
    if not all_nums:
        return None, qty

    candidates = []
    for n in all_nums:
        try:
            val = Decimal(n)
            candidates.append(val)
        except Exception:
            continue

    if not candidates:
        return None, qty

    if qty_match and len(candidates) > 1:
        non_qty = [c for c in candidates if c != qty]
        if non_qty:
            return non_qty[-1], qty

    return candidates[-1], qty


class TextParser:
    """Parses natural-language conversational text into structured draft candidates."""

    @staticmethod
    def parse(text: str, default_date: datetime | None = None) -> DocumentExtractionData:
        dt = default_date or datetime.now(UTC)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        sales: list[CandidateSale] = []
        expenses: list[CandidateExpense] = []
        credits: list[CandidateCreditTransaction] = []
        invalid_rows: list[dict] = []

        # Keywords
        udhar_give_words = ["udhar diya", "udhar", "diya", "debit", "credit sale", "gave", "to"]
        udhar_recv_words = [
            "jama",
            "aaya",
            "mila",
            "pay kiya",
            "paid",
            "received",
            "repayment",
            "from",
        ]
        expense_words = [
            "bijli",
            "electricity",
            "rent",
            "kiraya",
            "salary",
            "tankha",
            "repair",
            "chai",
            "petrol",
            "expense",
        ]
        sale_words = ["sold", "sale", "becha", "bika"]

        for line_idx, line in enumerate(lines, start=1):
            line_lower = line.lower()

            # Skip page headers and document boundary markers
            if (
                re.match(r"^---?\s*page\s*\d+\s*---?$", line_lower)
                or re.match(r"^page\s*\d+$", line_lower)
                or re.match(r"^=+$", line_lower)
                or re.match(r"^-+$", line_lower)
            ):
                continue

            amount, qty = _extract_amount_and_qty(line)
            if amount is None or amount <= Decimal("0"):
                continue

            # 1. Expense check
            if any(w in line_lower for w in expense_words):
                cat = "OTHER"
                if "bijli" in line_lower or "electricity" in line_lower:
                    cat = "UTILITIES"
                elif "rent" in line_lower or "kiraya" in line_lower:
                    cat = "RENT"
                elif "salary" in line_lower or "tankha" in line_lower:
                    cat = "SALARY"

                expenses.append(
                    CandidateExpense(
                        category=cat,
                        amount=amount,
                        expense_date=dt,
                        description=line,
                        confidence=0.90,
                        source_row=line_idx,
                    )
                )
                continue

            # 2. Sales check
            if any(w in line_lower for w in sale_words):
                unit_price = (amount / qty) if qty > Decimal("0") else amount
                sales.append(
                    CandidateSale(
                        sale_number=f"TXT-{line_idx}",
                        sold_at=dt,
                        total_amount=amount,
                        source_row=line_idx,
                        confidence=0.85,
                        items=[
                            CandidateSaleItem(
                                product_name=line,
                                quantity=qty,
                                unit_price=unit_price,
                                total_amount=amount,
                            )
                        ],
                    )
                )
                continue

            # 3. Udhar check
            # Extract customer candidate name (words excluding keywords and digits)
            clean_name = re.sub(
                r"\b(ko|se|ka|ki|ke|udhar|jama|diya|mila|aaya|pay|kiya|paid|cash|upi|rs|inr|rupees)\b",
                "",
                line,
                flags=re.IGNORECASE,
            )
            clean_name = re.sub(r"[0-9₹\.,\-]", "", clean_name).strip()
            cust_name = clean_name or "Customer"

            is_give = any(w in line_lower for w in udhar_give_words)
            is_recv = any(w in line_lower for w in udhar_recv_words)

            ambiguity_flags = []
            if is_give and not is_recv:
                tx_type = "CHARGE"
            elif is_recv and not is_give:
                tx_type = "REPAYMENT"
            else:
                tx_type = "CHARGE"
                ambiguity_flags.append(
                    "AMBIGUOUS_DIRECTION: Transaction direction unclear (give vs receive)"
                )

            credits.append(
                CandidateCreditTransaction(
                    customer_candidate_name=cust_name,
                    transaction_type=tx_type,
                    amount=amount,
                    transaction_at=dt,
                    description=line,
                    snippet=line,
                    source_row=line_idx,
                    confidence=0.90 if not ambiguity_flags else 0.50,
                    ambiguity_flags=ambiguity_flags,
                    requires_owner_review=True,
                )
            )

        # Detect predominant extraction type
        if credits:
            ext_type = "UDHAR_LEDGER"
        elif sales:
            ext_type = "SALES"
        elif expenses:
            ext_type = "EXPENSES"
        else:
            ext_type = "MIXED"

        return DocumentExtractionData(
            extraction_type=ext_type,
            sales=sales,
            expenses=expenses,
            credit_transactions=credits,
            invalid_rows=invalid_rows,
        )
