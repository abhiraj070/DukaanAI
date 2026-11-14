"""Small dependency-free embedding and tenant-filtered hybrid retrieval service."""

import hashlib
import json
import math
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.document import UploadedDocument
from app.models.knowledge import KnowledgeChunk

EMBEDDING_VERSION = "hashing-256-v1"
TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def embed(text: str) -> list[float]:
    """Stable multilingual token-hash embedding; replaceable by hosted provider adapter."""
    vector = [0.0] * 256
    for token in TOKEN_RE.findall(text.casefold()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
        index = int.from_bytes(digest, "little") % len(vector)
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _document_pages(document: UploadedDocument) -> list[str]:
    path = Path(document.storage_path)
    content = path.read_bytes()
    if document.file_type == "PDF":
        import io

        from pypdf import PdfReader

        return [page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages]
    return [content.decode("utf-8", errors="replace")]


def index_document(db: Session, business_id: str, document: UploadedDocument) -> int:
    """Idempotently replace a document's tenant-local section chunks."""
    db.query(KnowledgeChunk).filter_by(business_id=business_id, document_id=document.id).delete(
        synchronize_session=False
    )
    sections: list[tuple[int | None, str]] = []
    for page_no, page in enumerate(_document_pages(document), start=1):
        for section in re.split(r"\n\s*\n", page):
            words = section.split()
            for start in range(0, len(words), 180):
                chunk = " ".join(words[start : start + 180]).strip()
                if chunk:
                    sections.append((page_no if document.file_type == "PDF" else None, chunk))
    for index, (page, content) in enumerate(sections):
        db.add(
            KnowledgeChunk(
                business_id=business_id,
                document_id=document.id,
                chunk_index=index,
                page_number=page,
                content=content,
                embedding=json.dumps(embed(content)),
                embedding_version=EMBEDDING_VERSION,
            )
        )
    db.flush()
    return len(sections)


def retrieve(db: Session, business_id: str, query: str, limit: int = 5) -> list[dict]:
    """Rank only this tenant's chunks using cosine plus lexical overlap."""
    terms = set(TOKEN_RE.findall(query.casefold()))
    qvec = embed(query)
    rows = (
        db.query(KnowledgeChunk, UploadedDocument.filename)
        .join(UploadedDocument, UploadedDocument.id == KnowledgeChunk.document_id)
        .filter(KnowledgeChunk.business_id == business_id)
        .all()
    )
    ranked = []
    for row, filename in rows:
        vector = json.loads(row.embedding)
        cosine = sum(a * b for a, b in zip(qvec, vector, strict=True))
        tokens = set(TOKEN_RE.findall(row.content.casefold()))
        lexical = len(terms & tokens) / max(1, len(terms))
        score = 0.65 * cosine + 0.35 * lexical
        if score > 0:
            ranked.append((score, row, filename))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "text": row.content,
            "score": round(score, 4),
            "source": filename,
            "document_id": row.document_id,
            "page": row.page_number,
        }
        for score, row, filename in ranked[:limit]
    ]
