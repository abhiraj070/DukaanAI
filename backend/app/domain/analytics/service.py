"""Deterministic Analytics Domain Service."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.models.catalogue import Product
from app.models.operations import Expense, Sale, SaleItem
from app.schemas.analytics import (
    AnalyticsFilter,
    KPIOverview,
    ProductPerformanceItem,
    ProductRankingResponse,
)
from app.schemas.common import DomainResult, EvidenceMetadata, round_curr, round_qty


class AnalyticsService:
    """Service computing authoritative historical business analytics and KPIs.

    Principles:
    - SQL queries and Python Decimal are the single source of truth for all metrics.
    - Never call revenue profit.
    - If product cost data is missing, COGS and Gross Profit are unavailable (None).
    """

    def __init__(self, db: Session, context: BusinessContext) -> None:
        self.db = db
        self.context = context
        self.business_id = context.business_id

    def get_kpis(self, filters: AnalyticsFilter | None = None) -> DomainResult[KPIOverview]:
        """Calculate high-level business KPIs over the requested date window."""
        sales_q = self.db.query(Sale).filter(
            Sale.business_id == self.business_id,
            Sale.status == "COMPLETED",
        )
        expenses_q = self.db.query(Expense).filter(Expense.business_id == self.business_id)

        date_start = None
        date_end = None

        if filters:
            if filters.start_date:
                sales_q = sales_q.filter(Sale.sold_at >= filters.start_date)
                expenses_q = expenses_q.filter(Expense.expense_date >= filters.start_date)
                date_start = filters.start_date
            if filters.end_date:
                sales_q = sales_q.filter(Sale.sold_at <= filters.end_date)
                expenses_q = expenses_q.filter(Expense.expense_date <= filters.end_date)
                date_end = filters.end_date

        sales = sales_q.all()
        expenses = expenses_q.all()

        gross_revenue = Decimal("0.00")
        total_units = Decimal("0.000")
        cogs_total = Decimal("0.00")
        has_missing_costs = False
        source_sale_ids = []

        for sale in sales:
            source_sale_ids.append(sale.id)
            gross_revenue += sale.total_amount
            for item in sale.items:
                total_units += item.quantity
                if item.unit_cost is not None:
                    cogs_total += item.quantity * item.unit_cost
                else:
                    has_missing_costs = True

        total_expenses = sum((e.amount for e in expenses), start=Decimal("0.00"))

        warnings = []
        if has_missing_costs:
            warnings.append(
                "One or more sold items lack recorded cost price; "
                "COGS and Gross Profit are reported as unavailable."
            )
            cogs = None
            gross_profit = None
            gross_margin_pct = None
            cost_available = False
        else:
            cogs = round_curr(cogs_total)
            gross_profit = round_curr(gross_revenue - cogs_total)
            if gross_revenue > Decimal("0.00"):
                gross_margin_pct = round_curr((gross_profit / gross_revenue) * Decimal("100.0"))
            else:
                gross_margin_pct = Decimal("0.00")
            cost_available = True

        overview = KPIOverview(
            gross_revenue=round_curr(gross_revenue),
            cogs=cogs,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin_pct,
            total_units_sold=round_qty(total_units),
            transaction_count=len(sales),
            total_expenses=round_curr(total_expenses),
            cost_data_available=cost_available,
            currency=self.context.currency,
        )

        evidence = EvidenceMetadata(
            source_record_ids=source_sale_ids[:100],  # sample IDs
            date_window_start=date_start,
            date_window_end=date_end,
            calculation_method="deterministic_sales_aggregation",
            assumptions=[
                "Only completed sales included",
                "Operating expenses aggregated from expense records",
            ],
            freshness_timestamp=datetime.now(UTC),
            warnings=warnings,
        )

        return DomainResult(data=overview, evidence=evidence)

    def get_product_performance(
        self, filters: AnalyticsFilter | None = None
    ) -> DomainResult[ProductRankingResponse]:
        """Calculate sales volume, revenue, and profitability rankings per SKU."""
        products = self.db.query(Product).filter(Product.business_id == self.business_id).all()

        sales_items_q = (
            self.db.query(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .filter(
                SaleItem.business_id == self.business_id,
                Sale.status == "COMPLETED",
            )
        )

        date_start = None
        date_end = None
        if filters:
            if filters.start_date:
                sales_items_q = sales_items_q.filter(Sale.sold_at >= filters.start_date)
                date_start = filters.start_date
            if filters.end_date:
                sales_items_q = sales_items_q.filter(Sale.sold_at <= filters.end_date)
                date_end = filters.end_date

        sale_items = sales_items_q.all()

        # Aggregate by product
        agg: dict[str, dict] = {}
        for p in products:
            agg[p.id] = {
                "product": p,
                "units_sold": Decimal("0.000"),
                "revenue": Decimal("0.00"),
                "cogs": Decimal("0.00"),
                "has_missing_cost": p.cost_price is None,
            }

        for item in sale_items:
            if item.product_id in agg:
                entry = agg[item.product_id]
                entry["units_sold"] += item.quantity
                entry["revenue"] += item.total_amount
                if item.unit_cost is not None:
                    entry["cogs"] += item.quantity * item.unit_cost
                else:
                    entry["has_missing_cost"] = True

        performance_items: list[ProductPerformanceItem] = []
        for _pid, data in agg.items():
            p: Product = data["product"]
            rev = data["revenue"]
            units = data["units_sold"]
            has_missing = data["has_missing_cost"]

            if not has_missing and rev > Decimal("0.00"):
                cogs_val = round_curr(data["cogs"])
                profit_val = round_curr(rev - cogs_val)
                margin_pct = (
                    round_curr((profit_val / rev) * Decimal("100.0"))
                    if rev > Decimal("0")
                    else Decimal("0.00")
                )
            elif not has_missing and rev == Decimal("0.00"):
                cogs_val = Decimal("0.00")
                profit_val = Decimal("0.00")
                margin_pct = Decimal("0.00")
            else:
                cogs_val = None
                profit_val = None
                margin_pct = None

            performance_items.append(
                ProductPerformanceItem(
                    product_id=p.id,
                    product_name=p.name,
                    sku=p.sku,
                    unit=p.unit,
                    units_sold=round_qty(units),
                    revenue=round_curr(rev),
                    cogs=cogs_val,
                    gross_profit=profit_val,
                    gross_margin_pct=margin_pct,
                    has_cost_price=not has_missing,
                )
            )

        top_revenue = sorted(performance_items, key=lambda x: x.revenue, reverse=True)[:10]
        top_units = sorted(performance_items, key=lambda x: x.units_sold, reverse=True)[:10]
        top_profit = sorted(
            [x for x in performance_items if x.gross_profit is not None],
            key=lambda x: x.gross_profit,  # type: ignore
            reverse=True,
        )[:10]
        slow_moving = sorted(performance_items, key=lambda x: x.units_sold)[:10]

        result = ProductRankingResponse(
            top_by_revenue=top_revenue,
            top_by_units=top_units,
            top_by_profit=top_profit,
            slow_moving=slow_moving,
        )

        evidence = EvidenceMetadata(
            source_record_ids=[item.id for item in sale_items[:50]],
            date_window_start=date_start,
            date_window_end=date_end,
            calculation_method="sku_level_aggregation",
            assumptions=["Products without sales recorded with 0 units"],
            freshness_timestamp=datetime.now(UTC),
            warnings=[],
        )

        return DomainResult(data=result, evidence=evidence)
