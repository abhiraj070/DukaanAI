"""PDF document text and table extraction parser using pypdf."""

import io
import re
from decimal import Decimal

import pypdf

from app.ingestion.parsers.text_parser import TextParser
from app.schemas.ingestion import (
    CandidateSale,
    CandidateSaleItem,
    DocumentExtractionData,
)


class PDFParser:
    """Extracts text and candidate invoices/transactions from PDF documents."""

    @staticmethod
    def parse(content: bytes) -> DocumentExtractionData:
        """Read PDF bytes and extract candidate records."""
        reader = pypdf.PdfReader(io.BytesIO(content))
        full_text = ""
        page_texts = []

        for page_idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            page_texts.append((page_idx, text))
            full_text += f"\n--- Page {page_idx} ---\n" + text

        # Check for typical bill/invoice line patterns: e.g. "Atta 10kg  2  450.00  900.00"
        sales_items: list[CandidateSaleItem] = []
        total_bill_amount = Decimal("0.00")

        # Line regex: <Description> <Qty> <Rate> <Amount>
        item_regex = re.compile(
            r"([A-Za-z0-9\s\.\-_]+?)\s+(\d+(?:\.\d+)?)\s+(?:₹|Rs\.?)?\s*(\d+(?:\.\d+)?)\s+(?:₹|Rs\.?)?\s*(\d+(?:\.\d+)?)",
            re.IGNORECASE,
        )

        for page_idx, page_text in page_texts:
            for line in page_text.splitlines():
                line = line.strip()
                match = item_regex.search(line)
                if match:
                    name = match.group(1).strip()
                    if name.lower() in [
                        "total",
                        "subtotal",
                        "tax",
                        "gst",
                        "cgst",
                        "sgst",
                        "discount",
                    ]:
                        continue
                    try:
                        qty = Decimal(match.group(2))
                        rate = Decimal(match.group(3))
                        amt = Decimal(match.group(4))
                        sales_items.append(
                            CandidateSaleItem(
                                product_name=name,
                                quantity=qty,
                                unit_price=rate,
                                total_amount=amt,
                                source_row=page_idx,
                            )
                        )
                        total_bill_amount += amt
                    except Exception:
                        pass

        if sales_items:
            sale = CandidateSale(
                sale_number="INV-PDF-EXTRACT",
                total_amount=total_bill_amount,
                items=sales_items,
                confidence=0.85,
            )
            return DocumentExtractionData(
                extraction_type="SALES",
                sales=[sale],
                expenses=[],
                credit_transactions=[],
            )

        # Fallback to textual natural-language parsing
        data = TextParser.parse(full_text)
        if not data.sales and not data.expenses and not data.credit_transactions:
            data.extraction_type = "SALES"
        return data
