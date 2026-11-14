"""Typed schemas for Core Business Analytics."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsFilter(BaseModel):
    """Filter parameters for analytics calculations."""

    period: str | None = Field(
        default=None,
        description="Period preset ('TODAY', 'LAST_7_DAYS', 'LAST_30_DAYS', 'THIS_MONTH')",
    )
    start_date: datetime | None = Field(default=None, description="Start date (UTC)")
    end_date: datetime | None = Field(default=None, description="End date (UTC)")
    category_id: str | None = Field(default=None, description="Optional category filter")


class KPIOverview(BaseModel):
    """Authoritative business KPI overview for a specified date window.

    Principles:
    - Never label revenue as profit.
    - If cost data is missing, gross profit is unavailable (None), not zero.
    - Receivables are not cash and repayments are not sales revenue.
    """

    model_config = ConfigDict(frozen=True)

    gross_revenue: Decimal = Field(
        ..., description="Total sales revenue (INR) across completed sales"
    )
    sales_returns: Decimal = Field(
        default=Decimal("0.00"),
        description="Total refunded / returned sales amount (INR)",
    )
    net_revenue: Decimal = Field(
        ..., description="Net Revenue = Gross Revenue - Sales Returns (INR)"
    )
    cogs: Decimal | None = Field(
        default=None,
        description="Cost of goods sold (INR); None if product cost records are missing",
    )
    gross_profit: Decimal | None = Field(
        default=None,
        description="Gross Profit = Net Revenue - COGS; None if cost data is unavailable",
    )
    gross_margin_pct: Decimal | None = Field(
        default=None,
        description="Gross Margin % = (Gross Profit / Net Revenue) * 100",
    )
    total_units_sold: Decimal = Field(..., description="Total physical units/packets/kg sold")
    transaction_count: int = Field(..., description="Count of completed sales bills")
    total_expenses: Decimal = Field(..., description="Total operating expenses recorded in window")
    net_profit_estimate: Decimal | None = Field(
        default=None,
        description="Net Profit = Gross Profit - Total Expenses; None if cost data is unavailable",
    )
    inventory_valuation: Decimal = Field(
        default=Decimal("0.00"),
        description="Current physical inventory valuation at cost (INR)",
    )
    inventory_turnover: Decimal | None = Field(
        default=None,
        description="Inventory Turnover = COGS / inventory_valuation (None if valuation is 0)",
    )
    missing_cost_items_count: int = Field(
        default=0,
        description="Number of sold line items lacking a recorded cost price",
    )
    cost_data_available: bool = Field(
        ..., description="True if 100% of sold products had reliable cost price records"
    )
    currency: str = Field(default="INR", description="Business default currency")
    period_label: str = Field(default="CUSTOM", description="Applied date period label")


class ProductPerformanceItem(BaseModel):
    """Performance metrics for an individual product SKU."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    product_name: str
    sku: str | None = None
    category_name: str | None = None
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


class CategoryPerformanceItem(BaseModel):
    """Performance metrics aggregated per product category."""

    model_config = ConfigDict(frozen=True)

    category_id: str | None = None
    category_name: str
    units_sold: Decimal
    revenue: Decimal
    cogs: Decimal | None = None
    gross_profit: Decimal | None = None
    gross_margin_pct: Decimal | None = None
    product_count: int


class CategoryBreakdownResponse(BaseModel):
    """Sales and profitability breakdown by product category."""

    model_config = ConfigDict(frozen=True)

    categories: list[CategoryPerformanceItem]
    total_revenue: Decimal


class AnalyticsTrendPoint(BaseModel):
    """Daily time-bucketed analytics metric for charting."""

    model_config = ConfigDict(frozen=True)

    date: str  # YYYY-MM-DD in Asia/Kolkata
    gross_revenue: Decimal
    net_revenue: Decimal
    cogs: Decimal | None = None
    gross_profit: Decimal | None = None
    expenses: Decimal
    units_sold: Decimal
    transaction_count: int


class AnalyticsTrendsResponse(BaseModel):
    """Historical timeline trends for charting."""

    model_config = ConfigDict(frozen=True)

    period_label: str
    points: list[AnalyticsTrendPoint]
    total_revenue: Decimal
    total_expenses: Decimal
