"""Typed schemas for Core Business Analytics."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsFilter(BaseModel):
    """Filter parameters for analytics calculations."""

    start_date: datetime | None = Field(default=None, description="Start date (UTC)")
    end_date: datetime | None = Field(default=None, description="End date (UTC)")
    category_id: str | None = Field(default=None, description="Optional category filter")


class KPIOverview(BaseModel):
    """Authoritative business KPI overview for a specified date window.

    Principles:
    - Never label revenue as profit.
    - If cost data is missing, gross profit is unavailable (None), not zero.
    """

    model_config = ConfigDict(frozen=True)

    gross_revenue: Decimal = Field(
        ..., description="Total sales revenue (INR) across completed sales"
    )
    cogs: Decimal | None = Field(
        default=None,
        description="Cost of goods sold (INR); None if product cost records are missing",
    )
    gross_profit: Decimal | None = Field(
        default=None,
        description="Gross Profit = Gross Revenue - COGS; None if cost data is unavailable",
    )
    gross_margin_pct: Decimal | None = Field(
        default=None,
        description="Gross Margin % = (Gross Profit / Gross Revenue) * 100",
    )
    total_units_sold: Decimal = Field(..., description="Total physical units/packets/kg sold")
    transaction_count: int = Field(..., description="Count of completed sales bills")
    total_expenses: Decimal = Field(..., description="Total operating expenses recorded in window")
    cost_data_available: bool = Field(
        ..., description="True if 100% of sold products had reliable cost price records"
    )
    currency: str = Field(default="INR", description="Business default currency")


class ProductPerformanceItem(BaseModel):
    """Performance metrics for an individual product SKU."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    product_name: str
    sku: str | None = None
    unit: str
    units_sold: Decimal
    revenue: Decimal
    cogs: Decimal | None = None
    gross_profit: Decimal | None = None
    gross_margin_pct: Decimal | None = None
    has_cost_price: bool


class ProductRankingResponse(BaseModel):
    """Top-performing and slow-moving product rankings."""

    model_config = ConfigDict(frozen=True)

    top_by_revenue: list[ProductPerformanceItem]
    top_by_units: list[ProductPerformanceItem]
    top_by_profit: list[ProductPerformanceItem]
    slow_moving: list[ProductPerformanceItem]
