"""Editable festival calendar and evidence-backed uplift endpoints."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.context import BusinessContext, get_business_context
from app.db.session import get_db
from app.domain.festivals.service import FestivalIntelligenceService
from app.schemas.common import DomainResult
from app.schemas.festivals import FestivalEventInput, FestivalEventResponse, FestivalUpliftResult

router = APIRouter(prefix="/festivals", tags=["Festival Intelligence"])


@router.get("/calendar", response_model=list[FestivalEventResponse])
def list_calendar(
    context: BusinessContext = Depends(get_business_context), db: Session = Depends(get_db)
):
    return FestivalIntelligenceService(db, context).list_events()


@router.post("/calendar", response_model=FestivalEventResponse)
def create_event(
    payload: FestivalEventInput,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return FestivalIntelligenceService(db, context).save_event(payload)


@router.put("/calendar/{event_id}", response_model=FestivalEventResponse)
def update_event(
    event_id: str,
    payload: FestivalEventInput,
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return FestivalIntelligenceService(db, context).save_event(payload, event_id)


@router.get("/calendar/{event_id}/uplift", response_model=DomainResult[FestivalUpliftResult])
def get_uplift(
    event_id: str,
    assumed_uplift_pct: Decimal | None = Query(default=None, ge=-100, le=1000),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return FestivalIntelligenceService(db, context).estimate_uplift(event_id, assumed_uplift_pct)
