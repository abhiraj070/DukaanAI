"""Tenant-scoped knowledge retrieval and AI Decision Lab endpoints."""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import BusinessContext, get_business_context
from app.core.errors import BadRequestError, NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.domain.decision.agent import AgentDependencies, create_decision_agent
from app.domain.knowledge.service import index_document, retrieve
from app.models.document import UploadedDocument
from app.models.knowledge import Conversation
from app.schemas.decision import DecisionRequest, DecisionResponse

router = APIRouter(prefix="/decision", tags=["AI Decision Lab"])


@router.post("/documents/{document_id}/index")
def index_knowledge_document(
    document_id: str,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> dict:
    document = (
        db.query(UploadedDocument)
        .filter_by(id=document_id, business_id=context.business_id)
        .first()
    )
    if not document:
        raise NotFoundError("Document not found in this business")
    try:
        count = index_document(db, context.business_id, document)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise BadRequestError(f"Document could not be indexed: {exc}") from exc
    return {"document_id": document.id, "chunks_indexed": count, "status": "indexed"}


@router.get("/search")
def search_knowledge(
    q: str = Query(min_length=2, max_length=1000),
    limit: int = Query(default=5, ge=1, le=20),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> dict:
    return {"results": retrieve(db, context.business_id, q, limit)}


@router.post("/ask", response_model=DecisionResponse)
def ask_decision_lab(
    payload: DecisionRequest,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DecisionResponse:
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise ServiceUnavailableError("AI provider is not configured")
    try:
        from pydantic_ai.usage import UsageLimits
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        model = GoogleModel(
            "gemini-2.5-flash", provider=GoogleProvider(api_key=settings.GEMINI_API_KEY)
        )
        agent = create_decision_agent(model)
        result = agent.run_sync(
            payload.question,
            deps=AgentDependencies(db=db, context=context),
            usage_limits=UsageLimits(request_limit=settings.AI_MAX_REQUESTS),
            model_settings={"timeout": settings.AI_TIMEOUT_SECONDS, "max_tokens": 1200},
        )
    except Exception as exc:
        raise ServiceUnavailableError("AI decision service is temporarily unavailable") from exc
    response = result.output
    db.add(
        Conversation(
            business_id=context.business_id,
            user_id=context.user_id,
            question=payload.question,
            response_json=response.model_dump_json(),
        )
    )
    db.commit()
    return response


@router.get("/history")
def decision_history(
    limit: int = Query(default=20, ge=1, le=100),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> dict:
    rows = (
        db.query(Conversation)
        .filter_by(business_id=context.business_id, user_id=context.user_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "question": row.question,
                "response": json.loads(row.response_json),
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }
