"""Quick natural language text ingestion and tabular file preview endpoints."""

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.context import BusinessContext, get_business_context
from app.core.errors import BadRequestError
from app.db.session import get_db
from app.ingestion.parsers.csv_parser import CSVParser
from app.ingestion.parsers.text_parser import TextParser
from app.ingestion.parsers.xlsx_parser import XLSXParser
from app.models.document import DocumentExtraction, UploadedDocument
from app.schemas.ingestion import (
    DocumentExtractionData,
    ImportPreviewResponse,
    NaturalLanguageIngestionRequest,
)

router = APIRouter(prefix="/ingestion", tags=["Documents & Ingestion"])


@router.post("/text", response_model=DocumentExtractionData)
def parse_natural_language_text(
    payload: NaturalLanguageIngestionRequest,
    save_draft: bool = Query(
        default=False,
        description="Whether to persist as a draft document for review/confirmation",
    ),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DocumentExtractionData:
    """Parse Hinglish, Hindi, or English conversational entries into candidate records."""
    extraction_data = TextParser.parse(payload.text, default_date=payload.default_date)

    if save_draft:
        import hashlib

        content_bytes = payload.text.encode("utf-8")
        sha256 = hashlib.sha256(content_bytes).hexdigest()

        doc = UploadedDocument(
            business_id=context.business_id,
            filename="quick_note.txt",
            file_type="TEXT",
            file_size_bytes=len(content_bytes),
            sha256_hash=sha256,
            storage_path="virtual://quick_note",
            status="PROCESSED",
            uploaded_by=context.user_id,
        )
        db.add(doc)
        db.flush()

        ambiguity_count = sum(len(c.ambiguity_flags) for c in extraction_data.credit_transactions)

        extraction = DocumentExtraction(
            document_id=doc.id,
            business_id=context.business_id,
            extraction_type=extraction_data.extraction_type,
            extraction_version="v1.0",
            raw_extracted_json=payload.text,
            validated_candidates_json=extraction_data.model_dump_json(),
            ambiguity_count=ambiguity_count,
            is_confirmed=False,
        )
        db.add(extraction)
        db.commit()

    return extraction_data


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import_file(
    file: UploadFile = File(...),
    context: BusinessContext = Depends(get_business_context),
) -> ImportPreviewResponse:
    """Instant preview of CSV or XLSX spreadsheet without committing to disk."""
    filename = file.filename or "unknown.csv"
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

    if ext not in [".csv", ".xlsx", ".xls"]:
        raise BadRequestError("Only CSV and XLSX files are supported for instant preview")

    content = await file.read()
    if not content:
        raise BadRequestError("Uploaded file is empty")

    file_type = "CSV" if ext == ".csv" else "XLSX"
    if file_type == "CSV":
        candidates = CSVParser.parse(content)
    else:
        candidates = XLSXParser.parse(content)

    valid_count = (
        len(candidates.sales) + len(candidates.expenses) + len(candidates.credit_transactions)
    )
    invalid_count = len(candidates.invalid_rows)
    total_count = valid_count + invalid_count

    return ImportPreviewResponse(
        filename=filename,
        file_type=file_type,
        detected_type=candidates.extraction_type,
        total_rows=total_count,
        valid_rows_count=valid_count,
        invalid_rows_count=invalid_count,
        candidates=candidates,
    )
