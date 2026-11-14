"""API endpoints for document upload, processing, review, and ledger posting."""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.context import BusinessContext, get_business_context
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.db.session import get_db
from app.ingestion.parsers.csv_parser import CSVParser
from app.ingestion.parsers.pdf_parser import PDFParser
from app.ingestion.parsers.text_parser import TextParser
from app.ingestion.parsers.xlsx_parser import XLSXParser
from app.ingestion.posting import PostingService
from app.ingestion.storage import StorageService
from app.models.document import DocumentExtraction, UploadedDocument
from app.schemas.ingestion import (
    DocumentConfirmRequest,
    DocumentConfirmResponse,
    DocumentExtractionData,
    DocumentExtractionResponse,
    DocumentListResponse,
    UploadDocumentResponse,
    UploadedDocumentSummary,
)

router = APIRouter(prefix="/documents", tags=["Documents & Ingestion"])


def _extract_from_content(file_type: str, content: bytes) -> DocumentExtractionData:
    """Dispatch file content to the appropriate format parser."""
    if file_type == "CSV":
        return CSVParser.parse(content)
    elif file_type == "XLSX":
        return XLSXParser.parse(content)
    elif file_type == "PDF":
        return PDFParser.parse(content)
    elif file_type == "TEXT":
        text = content.decode("utf-8", errors="replace")
        return TextParser.parse(text)
    else:
        # For images or unsupported direct formats, fallback to text parser or empty draft
        text = content.decode("utf-8", errors="replace")
        return TextParser.parse(text)


def _count_ambiguities(data: DocumentExtractionData) -> int:
    """Calculate total number of unresolved ambiguities requiring owner review."""
    count = 0
    for c in data.credit_transactions:
        if c.ambiguity_flags:
            count += len(c.ambiguity_flags)
    return count


@router.post("/upload", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    auto_process: bool = Form(default=True),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> UploadDocumentResponse:
    """Upload a file, compute SHA-256 fingerprint, store securely, and extract candidates."""
    content = await file.read()
    if not content:
        raise BadRequestError("Uploaded file is empty")

    storage_svc = StorageService()
    storage_path, file_type, sha256_hash, file_size = storage_svc.validate_and_save(
        business_id=context.business_id,
        filename=file.filename or "unknown",
        content=content,
    )

    # Check for duplicate within the same business
    existing_doc = (
        db.query(UploadedDocument)
        .filter(
            UploadedDocument.business_id == context.business_id,
            UploadedDocument.sha256_hash == sha256_hash,
        )
        .first()
    )
    if existing_doc:
        return UploadDocumentResponse(
            document_id=existing_doc.id,
            filename=existing_doc.filename,
            file_type=existing_doc.file_type,
            file_size_bytes=existing_doc.file_size_bytes,
            sha256_hash=existing_doc.sha256_hash,
            status=existing_doc.status,
            message=(
                "Duplicate document detected (identical SHA-256 fingerprint). "
                "Existing document referenced."
            ),
        )

    doc = UploadedDocument(
        business_id=context.business_id,
        filename=file.filename or "uploaded_file",
        file_type=file_type,
        file_size_bytes=file_size,
        sha256_hash=sha256_hash,
        storage_path=storage_path,
        status="PENDING",
        uploaded_by=context.user_id,
    )
    db.add(doc)
    db.flush()

    if auto_process:
        try:
            extraction_data = _extract_from_content(file_type, content)
            ambiguity_count = _count_ambiguities(extraction_data)

            extraction = DocumentExtraction(
                document_id=doc.id,
                business_id=context.business_id,
                extraction_type=extraction_data.extraction_type,
                extraction_version="v1.0",
                raw_extracted_json=None,
                validated_candidates_json=extraction_data.model_dump_json(),
                ambiguity_count=ambiguity_count,
                is_confirmed=False,
            )
            db.add(extraction)
            doc.status = "PROCESSED"
        except Exception as e:
            doc.status = "FAILED"
            db.commit()
            raise BadRequestError(f"Failed to process document content: {str(e)}") from e

    db.commit()

    return UploadDocumentResponse(
        document_id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        sha256_hash=doc.sha256_hash,
        status=doc.status,
        message="File uploaded and processed into draft candidates successfully.",
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """List uploaded documents for the authenticated tenant."""
    query = db.query(UploadedDocument).filter(UploadedDocument.business_id == context.business_id)
    if status:
        query = query.filter(UploadedDocument.status == status)

    total = query.count()
    docs = query.order_by(UploadedDocument.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for doc in docs:
        extraction = (
            db.query(DocumentExtraction)
            .filter(
                DocumentExtraction.document_id == doc.id,
                DocumentExtraction.business_id == context.business_id,
            )
            .first()
        )
        items.append(
            UploadedDocumentSummary(
                id=doc.id,
                filename=doc.filename,
                file_type=doc.file_type,
                file_size_bytes=doc.file_size_bytes,
                sha256_hash=doc.sha256_hash,
                status=doc.status,
                ambiguity_count=extraction.ambiguity_count if extraction else 0,
                is_confirmed=extraction.is_confirmed if extraction else False,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
            )
        )

    return DocumentListResponse(documents=items, total=total)


@router.get("/{document_id}", response_model=DocumentExtractionResponse)
def get_document_extraction(
    document_id: str,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DocumentExtractionResponse:
    """Retrieve extracted candidate records and provenance for owner review."""
    doc = (
        db.query(UploadedDocument)
        .filter(
            UploadedDocument.id == document_id,
            UploadedDocument.business_id == context.business_id,
        )
        .first()
    )
    if not doc:
        raise NotFoundError(f"Document {document_id} not found in this business")

    extraction = (
        db.query(DocumentExtraction)
        .filter(
            DocumentExtraction.document_id == document_id,
            DocumentExtraction.business_id == context.business_id,
        )
        .first()
    )
    if not extraction:
        raise NotFoundError(f"Extractions for document {document_id} not found")

    candidates_data = DocumentExtractionData.model_validate_json(
        extraction.validated_candidates_json
    )

    return DocumentExtractionResponse(
        document_id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        sha256_hash=doc.sha256_hash,
        status=doc.status,
        extraction_type=extraction.extraction_type,
        extraction_version=extraction.extraction_version,
        data=candidates_data,
        ambiguity_count=extraction.ambiguity_count,
        is_confirmed=extraction.is_confirmed,
        confirmed_at=extraction.confirmed_at,
    )


@router.patch("/{document_id}/extraction", response_model=DocumentExtractionResponse)
def update_document_extraction(
    document_id: str,
    payload: DocumentExtractionData,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DocumentExtractionResponse:
    """Allow owner to edit candidate draft records prior to confirmation."""
    doc = (
        db.query(UploadedDocument)
        .filter(
            UploadedDocument.id == document_id,
            UploadedDocument.business_id == context.business_id,
        )
        .first()
    )
    if not doc:
        raise NotFoundError(f"Document {document_id} not found in this business")

    extraction = (
        db.query(DocumentExtraction)
        .filter(
            DocumentExtraction.document_id == document_id,
            DocumentExtraction.business_id == context.business_id,
        )
        .first()
    )
    if not extraction:
        raise NotFoundError(f"Extractions for document {document_id} not found")

    if extraction.is_confirmed:
        raise ConflictError("Cannot edit extractions for an already confirmed document")

    ambiguity_count = _count_ambiguities(payload)

    extraction.extraction_type = payload.extraction_type
    extraction.validated_candidates_json = payload.model_dump_json()
    extraction.ambiguity_count = ambiguity_count
    db.commit()

    return DocumentExtractionResponse(
        document_id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        sha256_hash=doc.sha256_hash,
        status=doc.status,
        extraction_type=extraction.extraction_type,
        extraction_version=extraction.extraction_version,
        data=payload,
        ambiguity_count=ambiguity_count,
        is_confirmed=extraction.is_confirmed,
        confirmed_at=extraction.confirmed_at,
    )


@router.post("/{document_id}/confirm", response_model=DocumentConfirmResponse)
def confirm_document(
    document_id: str,
    payload: DocumentConfirmRequest | None = None,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DocumentConfirmResponse:
    """Post owner-confirmed candidates transactionally and idempotently into domain tables."""
    effective_payload = payload or DocumentConfirmRequest()
    posting_svc = PostingService(db, context)
    return posting_svc.post_confirmation(document_id, effective_payload)
