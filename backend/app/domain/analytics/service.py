"""Deterministic Analytics Domain Service."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.domain.analytics.date_ranges import resolve_date_window, to_kolkata_date_str
from app.domain.inventory.service import InventoryService
from app.models.catalogue import Category, Product
from app.models.operations import Expense, Sale, SaleItem
from app.schemas.analytics import (
    AnalyticsFilter,
    AnalyticsTrendPoint,
    AnalyticsTrendsResponse,
    CategoryBreakdownResponse,
    CategoryPerformanceItem,
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
    - Receivables are not cash; repayments are not sales revenue.
    """

    def __init__(self, db: Session, context: BusinessContext) -> None:
        self.db = db
        self.context = context
        self.business_id = context.business_id
        self.inv_service = InventoryService(db, context)

    def get_kpis(self, filters: AnalyticsFilter | None = None) -> DomainResult[KPIOverview]:
        """Calculate high-level business KPIs over the requested date window."""
        start_date = filters.start_date if filters else None
        end_date = filters.end_date if filters else None
        period_str = filters.period if filters else None

        date_start, date_end, period_label = resolve_date_window(
            period=period_str,
            start_date=start_date,
            end_date=end_date,
            tz_name=self.context.timezone,
        )

        sales_completed_q = self.db.query(Sale).filter(
            Sale.business_id == self.business_id,
            Sale.status == "COMPLETED",
        )
        sales_returned_q = self.db.query(Sale).filter(
            Sale.business_id == self.business_id,
            Sale.status == "RETURNED",
        )
        expenses_q = self.db.query(Expense).filter(Expense.business_id == self.business_id)

        if date_start:
            sales_completed_q = sales_completed_q.filter(Sale.sold_at >= date_start)
            sales_returned_q = sales_returned_q.filter(Sale.sold_at >= date_start)
            expenses_q = expenses_q.filter(Expense.expense_date >= date_start)
        if date_end:
            sales_completed_q = sales_completed_q.filter(Sale.sold_at <= date_end)
            sales_returned_q = sales_returned_q.filter(Sale.sold_at <= date_end)
            expenses_q = expenses_q.filter(Expense.expense_date <= date_end)

        completed_sales = sales_completed_q.all()
        returned_sales = sales_returned_q.all()
        expenses = expenses_q.all()

        gross_revenue = Decimal("0.00")
        total_units = Decimal("0.000")
        cogs_total = Decimal("0.00")
        has_missing_costs = False
        missing_cost_items_count = 0
        source_sale_ids = []

        for sale in completed_sales:
            source_sale_ids.append(sale.id)
            gross_revenue += sale.total_amount
            for item in sale.items:
                total_units += item.quantity
                if item.unit_cost is not None:
                    cogs_total += item.quantity * item.unit_cost
                else:
                    has_missing_costs = True
                    missing_cost_items_count += 1

        sales_returns_amount = sum((s.total_amount for s in returned_sales), start=Decimal("0.00"))
        net_revenue = gross_revenue - sales_returns_amount
        total_expenses = sum((e.amount for e in expenses), start=Decimal("0.00"))

        # Inventory valuation from inventory movements
        inv_summary = self.inv_service.get_inventory_status().data
        inventory_valuation = inv_summary.total_inventory_valuation or Decimal("0.00")

        warnings = []
        if has_missing_costs:
            warnings.append(
                f"Cost price missing for {missing_cost_items_count} sold item(s); "
                "COGS, Gross Profit, and Gross Margin are reported as unavailable (None)."
            )
            cogs = None
            gross_profit = None
            gross_margin_pct = None
            net_profit_estimate = None
            inventory_turnover = None
            cost_available = False
        else:
            cogs = round_curr(cogs_total)
            gross_profit = round_curr(net_revenue - cogs_total)
            if net_revenue > Decimal("0.00"):
                gross_margin_pct = round_curr((gross_profit / net_revenue) * Decimal("100.0"))
            else:
                gross_margin_pct = Decimal("0.00")
            net_profit_estimate = round_curr(gross_profit - total_expenses)

            if inventory_valuation > Decimal("0.00"):
                inventory_turnover = round_curr(cogs / inventory_valuation)
            else:
                inventory_turnover = None
            cost_available = True

        overview = KPIOverview(
            gross_revenue=round_curr(gross_revenue),
            sales_returns=round_curr(sales_returns_amount),
            net_revenue=round_curr(net_revenue),
            cogs=cogs,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin_pct,
            total_units_sold=round_qty(total_units),
            transaction_count=len(completed_sales),
            total_expenses=round_curr(total_expenses),
            net_profit_estimate=net_profit_estimate,
            inventory_valuation=round_curr(inventory_valuation),
            inventory_turnover=inventory_turnover,
            missing_cost_items_count=missing_cost_items_count,
            cost_data_available=cost_available,
            currency=self.context.currency,
            period_label=period_label,
        )

        evidence = EvidenceMetadata(
            source_record_ids=source_sale_ids[:100],
            date_window_start=date_start,
            date_window_end=date_end,
            calculation_method="deterministic_sales_aggregation",
            assumptions=[
                "Completed sales constitute gross revenue",
                "Returned sales deduct from gross revenue to yield net revenue",
                "Operating expenses aggregated from recorded expenses",
                "Receivables are kept distinct from cash and sales revenue",
            ],
            freshness_timestamp=datetime.now(UTC),
            warnings=warnings,
        )

        return DomainResult(data=overview, evidence=evidence)

    def get_product_performance(
        self, filters: AnalyticsFilter | None = None
    ) -> DomainResult[ProductRankingResponse]:
        """Calculate sales volume, revenue, and profitability rankings per SKU."""
        start_date = filters.start_date if filters else None
        end_date = filters.end_date if filters else None
        period_str = filters.period if filters else None

        date_start, date_end, _ = resolve_date_window(
            period=period_str,
            start_date=start_date,
            end_date=end_date,
            tz_name=self.context.timezone,
        )

        products = self.db.query(Product).filter(Product.business_id == self.business_id).all()

        sales_items_q = (
            self.db.query(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .filter(
                SaleItem.business_id == self.business_id,
                Sale.status == "COMPLETED",
            )
        )

        if date_start:
            sales_items_q = sales_items_q.filter(Sale.sold_at >= date_start)
        if date_end:
            sales_items_q = sales_items_q.filter(Sale.sold_at <= date_end)

        sale_items = sales_items_q.all()

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
                    category_name=p.category.name if p.category else "General",
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

    def get_category_breakdown(
        self, filters: AnalyticsFilter | None = None
    ) -> DomainResult[CategoryBreakdownResponse]:
        """Aggregate revenue and profitability by product category."""
        start_date = filters.start_date if filters else None
        end_date = filters.end_date if filters else None
        period_str = filters.period if filters else None

        date_start, date_end, _ = resolve_date_window(
            period=period_str,
            start_date=start_date,
            end_date=end_date,
            tz_name=self.context.timezone,
        )

        categories = self.db.query(Category).filter(Category.business_id == self.business_id).all()

        cat_agg: dict[str | None, dict] = {
            c.id: {
                "name": c.name,
                "units": Decimal("0.000"),
                "revenue": Decimal("0.00"),
                "cogs": Decimal("0.00"),
                "has_missing_cost": False,
                "product_count": 0,
            }
            for c in categories
        }
        # Add entry for uncategorized
        cat_agg[None] = {
            "name": "General / Uncategorized",
            "units": Decimal("0.000"),
            "revenue": Decimal("0.00"),
            "cogs": Decimal("0.00"),
            "has_missing_cost": False,
            "product_count": 0,
        }

        # Count products per category
        products = self.db.query(Product).filter(Product.business_id == self.business_id).all()
        for p in products:
            if p.category_id in cat_agg:
                cat_agg[p.category_id]["product_count"] += 1
            else:
                cat_agg[None]["product_count"] += 1

        sales_items_q = (
            self.db.query(SaleItem, Product)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .filter(
                SaleItem.business_id == self.business_id,
                Sale.status == "COMPLETED",
            )
        )

        if date_start:
            sales_items_q = sales_items_q.filter(Sale.sold_at >= date_start)
        if date_end:
            sales_items_q = sales_items_q.filter(Sale.sold_at <= date_end)

        rows = sales_items_q.all()
        total_revenue = Decimal("0.00")

        for item, prod in rows:
            c_id = prod.category_id if prod.category_id in cat_agg else None
            entry = cat_agg[c_id]
            entry["units"] += item.quantity
            entry["revenue"] += item.total_amount
            total_revenue += item.total_amount

            if item.unit_cost is not None:
                entry["cogs"] += item.quantity * item.unit_cost
            else:
                entry["has_missing_cost"] = True

        items: list[CategoryPerformanceItem] = []
        for cat_id, data in cat_agg.items():
            if data["revenue"] == Decimal("0.00") and data["product_count"] == 0:
                continue

            rev = data["revenue"]
            units = data["units"]
            if not data["has_missing_cost"] and rev > Decimal("0.00"):
                cogs_val = round_curr(data["cogs"])
                profit_val = round_curr(rev - cogs_val)
                margin_val = (
                    round_curr((profit_val / rev) * Decimal("100.0"))
                    if rev > Decimal("0")
                    else Decimal("0.00")
                )
            else:
                cogs_val = None
                profit_val = None
                margin_val = None

            items.append(
                CategoryPerformanceItem(
                    category_id=cat_id,
                    category_name=data["name"],
                    units_sold=round_qty(units),
                    revenue=round_curr(rev),
                    cogs=cogs_val,
                    gross_profit=profit_val,
                    gross_margin_pct=margin_val,
                    product_count=data["product_count"],
                )
            )

        items.sort(key=lambda x: x.revenue, reverse=True)
        resp = CategoryBreakdownResponse(categories=items, total_revenue=round_curr(total_revenue))

        evidence = EvidenceMetadata(
            source_record_ids=[c.id for c in categories],
            date_window_start=date_start,
            date_window_end=date_end,
            calculation_method="category_level_aggregation",
            assumptions=["Products without category assigned to General"],
            freshness_timestamp=datetime.now(UTC),
            warnings=[],
        )

        return DomainResult(data=resp, evidence=evidence)

    def get_analytics_trends(
        self, filters: AnalyticsFilter | None = None
    ) -> DomainResult[AnalyticsTrendsResponse]:
        """Aggregate daily time-bucketed trend points for timeline charts."""
        start_date = filters.start_date if filters else None
        end_date = filters.end_date if filters else None
        period_str = filters.period if filters else None

        date_start, date_end, period_label = resolve_date_window(
            period=period_str or "LAST_30_DAYS",
            start_date=start_date,
            end_date=end_date,
            tz_name=self.context.timezone,
        )

        sales_q = self.db.query(Sale).filter(
            Sale.business_id == self.business_id,
            Sale.status.in_(["COMPLETED", "RETURNED"]),
        )
        expenses_q = self.db.query(Expense).filter(Expense.business_id == self.business_id)

        if date_start:
            sales_q = sales_q.filter(Sale.sold_at >= date_start)
            expenses_q = expenses_q.filter(Expense.expense_date >= date_start)
        if date_end:
            sales_q = sales_q.filter(Sale.sold_at <= date_end)
            expenses_q = expenses_q.filter(Expense.expense_date <= date_end)

        sales = sales_q.order_by(Sale.sold_at.asc()).all()
        expenses = expenses_q.order_by(Expense.expense_date.asc()).all()

        daily_agg: dict[str, dict] = {}

        for sale in sales:
            d_str = to_kolkata_date_str(sale.sold_at)
            if d_str not in daily_agg:
                daily_agg[d_str] = {
                    "gross_revenue": Decimal("0.00"),
                    "returns": Decimal("0.00"),
                    "cogs": Decimal("0.00"),
                    "has_missing_cost": False,
                    "expenses": Decimal("0.00"),
                    "units": Decimal("0.000"),
                    "count": 0,
                }

            entry = daily_agg[d_str]
            if sale.status == "COMPLETED":
                entry["gross_revenue"] += sale.total_amount
                entry["count"] += 1
                for item in sale.items:
                    entry["units"] += item.quantity
                    if item.unit_cost is not None:
                        entry["cogs"] += item.quantity * item.unit_cost
                    else:
                        entry["has_missing_cost"] = True
            elif sale.status == "RETURNED":
                entry["returns"] += sale.total_amount

        for exp in expenses:
            d_str = to_kolkata_date_str(exp.expense_date)
            if d_str not in daily_agg:
                daily_agg[d_str] = {
                    "gross_revenue": Decimal("0.00"),
                    "returns": Decimal("0.00"),
                    "cogs": Decimal("0.00"),
                    "has_missing_cost": False,
                    "expenses": Decimal("0.00"),
                    "units": Decimal("0.000"),
                    "count": 0,
                }
            daily_agg[d_str]["expenses"] += exp.amount

        points: list[AnalyticsTrendPoint] = []
        tot_rev = Decimal("0.00")
        tot_exp = Decimal("0.00")

        for d_str in sorted(daily_agg.keys()):
            val = daily_agg[d_str]
            gross = val["gross_revenue"]
            net = gross - val["returns"]
            cogs_val = round_curr(val["cogs"]) if not val["has_missing_cost"] else None
            profit_val = round_curr(net - val["cogs"]) if not val["has_missing_cost"] else None

            tot_rev += net
            tot_exp += val["expenses"]

            points.append(
                AnalyticsTrendPoint(
                    date=d_str,
                    gross_revenue=round_curr(gross),
                    net_revenue=round_curr(net),
                    cogs=cogs_val,
                    gross_profit=profit_val,
                    expenses=round_curr(val["expenses"]),
                    units_sold=round_qty(val["units"]),
                    transaction_count=val["count"],
                )
            )

        resp = AnalyticsTrendsResponse(
            period_label=period_label,
            points=points,
            total_revenue=round_curr(tot_rev),
            total_expenses=round_curr(tot_exp),
        )

        evidence = EvidenceMetadata(
            source_record_ids=[s.id for s in sales[:50]],
            date_window_start=date_start,
            date_window_end=date_end,
            calculation_method="daily_bucketed_timeline_aggregation",
            assumptions=["Days grouped by Asia/Kolkata timezone"],
            freshness_timestamp=datetime.now(UTC),
            warnings=[],
        )

        return DomainResult(data=resp, evidence=evidence)
