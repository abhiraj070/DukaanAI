"""Excel XLSX document parser using openpyxl."""

import io

import openpyxl

from app.ingestion.parsers.csv_parser import CSVParser
from app.schemas.ingestion import DocumentExtractionData


class XLSXParser:
    """Parses Excel workbooks into structured candidate records."""

    @staticmethod
    def parse(content: bytes) -> DocumentExtractionData:
        """Read bytes of an XLSX file and extract candidates."""
        workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet = workbook.active
        if sheet is None:
            return DocumentExtractionData(extraction_type="MIXED")

        # Convert sheet rows to string rows
        raw_rows: list[list[str]] = []
        for row in sheet.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                raw_rows.append([str(cell).strip() if cell is not None else "" for cell in row])

        if not raw_rows:
            return DocumentExtractionData(extraction_type="MIXED")

        # Convert to virtual CSV buffer and delegate to table parsing logic
        import csv

        output = io.StringIO()
        writer = csv.writer(output)
        for r in raw_rows:
            writer.writerow(r)

        csv_bytes = output.getvalue().encode("utf-8")
        return CSVParser.parse(csv_bytes)
