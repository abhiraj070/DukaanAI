"""Inventory status and forecast endpoints."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.context import BusinessContext, get_business_context
from app.core.errors import BadRequestError
from app.db.session import get_db
from app.domain.festivals.service import FestivalIntelligenceService
from app.domain.inventory.service import InventoryService
from app.schemas.common import DomainResult
from app.schemas.inventory import DemandForecastResult

router = APIRouter(prefix="/inventory", tags=["Inventory Intelligence"])


@router.get("/products/{product_id}/forecast", response_model=DomainResult[DemandForecastResult])
def forecast_product(
    product_id: str,
    horizon_days: int = Query(default=14, ge=1, le=365),
    history_days: int = Query(default=30, ge=1, le=730),
    festival_event_id: str | None = None,
    festival_assumed_uplift_pct: Decimal | None = Query(default=None, ge=-100, le=1000),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    festival_uplift = Decimal("0.00")
    festival_source_ids: list[str] = []
    if festival_event_id:
        festival_result = FestivalIntelligenceService(db, context).estimate_uplift(
            festival_event_id, festival_assumed_uplift_pct
        )
        if festival_result.data.planning_uplift_pct is None:
            raise BadRequestError(
                "Festival history is insufficient; provide festival_assumed_uplift_pct."
            )
        festival_uplift = festival_result.data.planning_uplift_pct
        festival_source_ids = festival_result.evidence.source_record_ids
    elif festival_assumed_uplift_pct is not None:
        raise BadRequestError("festival_assumed_uplift_pct requires festival_event_id")
    return InventoryService(db, context).forecast_demand(
        product_id,
        horizon_days,
        history_days,
        festival_uplift_pct=festival_uplift,
        festival_source_ids=festival_source_ids,
    )
