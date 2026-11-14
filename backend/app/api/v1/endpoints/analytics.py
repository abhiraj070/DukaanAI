"""API endpoints for Core Business Analytics and reporting."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.context import BusinessContext, get_business_context
from app.db.session import get_db
from app.domain.analytics.service import AnalyticsService
from app.schemas.analytics import (
    AnalyticsFilter,
    AnalyticsTrendsResponse,
    CategoryBreakdownResponse,
    KPIOverview,
    ProductRankingResponse,
)
from app.schemas.common import DomainResult

router = APIRouter(prefix="/analytics", tags=["Analytics & KPIs"])


@router.get("/kpis", response_model=DomainResult[KPIOverview])
def get_kpis(
    period: str | None = Query(
        default="LAST_30_DAYS",
        description="Period preset ('TODAY', 'LAST_7_DAYS', 'LAST_30_DAYS', 'THIS_MONTH')",
    ),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    category_id: str | None = Query(default=None),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DomainResult[KPIOverview]:
    """Retrieve authoritative business KPIs with evidence metadata."""
    filters = AnalyticsFilter(
        period=period,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
    )
    service = AnalyticsService(db, context)
    return service.get_kpis(filters)


@router.get("/products", response_model=DomainResult[ProductRankingResponse])
def get_product_rankings(
    period: str | None = Query(default="LAST_30_DAYS"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DomainResult[ProductRankingResponse]:
    """Retrieve top-performing and slow-moving product rankings."""
    filters = AnalyticsFilter(
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    service = AnalyticsService(db, context)
    return service.get_product_performance(filters)


@router.get("/categories", response_model=DomainResult[CategoryBreakdownResponse])
def get_category_breakdown(
    period: str | None = Query(default="LAST_30_DAYS"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DomainResult[CategoryBreakdownResponse]:
    """Retrieve sales volume and profitability breakdown by product category."""
    filters = AnalyticsFilter(
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    service = AnalyticsService(db, context)
    return service.get_category_breakdown(filters)


@router.get("/trends", response_model=DomainResult[AnalyticsTrendsResponse])
def get_analytics_trends(
    period: str | None = Query(default="LAST_30_DAYS"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    context: BusinessContext = Depends(get_business_context),
    db: Session = Depends(get_db),
) -> DomainResult[AnalyticsTrendsResponse]:
    """Retrieve daily time-bucketed revenue, COGS, and expense trends for charting."""
    filters = AnalyticsFilter(
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    service = AnalyticsService(db, context)
    return service.get_analytics_trends(filters)
