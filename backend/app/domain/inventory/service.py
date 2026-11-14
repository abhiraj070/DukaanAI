"""Deterministic Inventory and Forecasting Domain Service."""

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.core.errors import NotFoundError
from app.models.catalogue import Product, SupplierProduct
from app.models.operations import Sale, SaleItem
from app.repositories.inventory import InventoryRepository
from app.schemas.common import DomainResult, EvidenceMetadata, round_curr, round_qty
from app.schemas.inventory import (
    DemandForecastResult,
    InventoryStatusItem,
    StoreInventorySummary,
)


class InventoryService:
    """Service providing authoritative stock status, cover calculations, and reorder intelligence.

    Principles:
    - On-hand stock is strictly reconciled from physical inventory movements.
    - Order quantities strictly respect supplier MOQ and pack sizes when configured.
    """

    def __init__(self, db: Session, context: BusinessContext) -> None:
        self.db = db
        self.context = context
        self.business_id = context.business_id
        self.inv_repo = InventoryRepository(db, context)

    def get_inventory_status(self) -> DomainResult[StoreInventorySummary]:
        """Fetch real-time stock levels, low-stock warnings, and inventory valuation."""
        products = (
            self.db.query(Product)
            .filter(Product.business_id == self.business_id, Product.is_active.is_(True))
            .all()
        )

        items: list[InventoryStatusItem] = []
        low_stock_count = 0
        stockout_count = 0
        total_valuation = Decimal("0.00")
        has_missing_costs = False

        for p in products:
            stock = self.inv_repo.get_stock(p.id)
            is_low = stock <= p.min_stock_level
            is_out = stock <= Decimal("0.000")

            if is_low:
                low_stock_count += 1
            if is_out:
                stockout_count += 1

            if p.cost_price is not None:
                if stock > Decimal("0.000"):
                    total_valuation += stock * p.cost_price
            else:
                has_missing_costs = True

            items.append(
                InventoryStatusItem(
                    product_id=p.id,
                    name=p.name,
                    sku=p.sku,
                    unit=p.unit,
                    selling_price=p.selling_price,
                    cost_price=p.cost_price,
                    on_hand_stock=round_qty(stock),
                    min_stock_level=p.min_stock_level,
                    reorder_quantity=p.reorder_quantity,
                    is_low_stock=is_low,
                    is_stockout=is_out,
                )
            )

        valuation_val = round_curr(total_valuation) if not has_missing_costs else None
        warnings = []
        if has_missing_costs:
            warnings.append(
                "Some active products lack cost price records; "
                "total valuation is reported as unavailable."
            )

        summary = StoreInventorySummary(
            total_products_count=len(products),
            low_stock_products_count=low_stock_count,
            stockout_products_count=stockout_count,
            total_inventory_valuation=valuation_val,
            products=items,
        )

        evidence = EvidenceMetadata(
            source_record_ids=[p.id for p in products[:50]],
            calculation_method="movement_reconciliation_sum",
            assumptions=["Stock reconciled from all confirmed inventory movements"],
            freshness_timestamp=datetime.now(UTC),
            warnings=warnings,
        )

        return DomainResult(data=summary, evidence=evidence)

    def forecast_demand(
        self, product_id: str, horizon_days: int = 14, history_days: int = 30
    ) -> DomainResult[DemandForecastResult]:
        """Compute rolling-average demand forecast, days of cover, and ROP."""
        product = (
            self.db.query(Product)
            .filter(Product.id == product_id, Product.business_id == self.business_id)
            .first()
        )
        if not product:
            raise NotFoundError(f"Product {product_id} not found in this business")

        current_stock = self.inv_repo.get_stock(product.id)

        # Sales history over the past history_days
        since_date = datetime.now(UTC) - timedelta(days=history_days)
        sale_items = (
            self.db.query(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .filter(
                SaleItem.business_id == self.business_id,
                SaleItem.product_id == product.id,
                Sale.sold_at >= since_date,
                Sale.status == "COMPLETED",
            )
            .all()
        )

        total_units_sold = sum((item.quantity for item in sale_items), start=Decimal("0.000"))
        daily_demand = total_units_sold / Decimal(str(history_days))

        lead_time_days = 3
        if product.supplier and product.supplier.lead_time_days:
            lead_time_days = product.supplier.lead_time_days

        safety_stock = product.min_stock_level
        reorder_point = round_qty((daily_demand * Decimal(str(lead_time_days))) + safety_stock)

        if daily_demand > Decimal("0.000"):
            days_of_cover = round_qty(current_stock / daily_demand)
            data_quality = "RELIABLE" if len(sale_items) >= 5 else "SPARSE"
        else:
            days_of_cover = None
            data_quality = "NO_HISTORY"

        is_reorder_needed = current_stock <= reorder_point

        # Supplier constraints: MOQ and pack size
        supplier_link = (
            self.db.query(SupplierProduct)
            .filter(
                SupplierProduct.business_id == self.business_id,
                SupplierProduct.product_id == product.id,
            )
            .first()
        )
        moq = supplier_link.moq if supplier_link else Decimal("1.000")
        pack_size = supplier_link.pack_size if supplier_link else Decimal("1.000")
        unit_cost = supplier_link.purchase_cost if supplier_link else product.cost_price

        suggested_qty = Decimal("0.000")
        if is_reorder_needed:
            # Replenish enough to cover horizon + safety stock - current stock
            target_stock = (daily_demand * Decimal(str(horizon_days))) + safety_stock
            raw_need = target_stock - current_stock
            if raw_need < moq:
                raw_need = moq

            # Round up to next multiple of pack_size
            if pack_size > Decimal("0"):
                multiplier = math.ceil(float(raw_need) / float(pack_size))
                suggested_qty = Decimal(str(multiplier)) * pack_size
            else:
                suggested_qty = raw_need

        estimated_cost = round_curr(suggested_qty * unit_cost) if unit_cost is not None else None

        result = DemandForecastResult(
            product_id=product.id,
            product_name=product.name,
            sku=product.sku,
            unit=product.unit,
            on_hand_stock=round_qty(current_stock),
            historical_daily_demand=round_qty(daily_demand),
            horizon_days=horizon_days,
            forecast_demand_period=round_qty(daily_demand * Decimal(str(horizon_days))),
            days_of_cover=days_of_cover,
            supplier_lead_time_days=lead_time_days,
            safety_stock=round_qty(safety_stock),
            reorder_point=reorder_point,
            is_reorder_recommended=is_reorder_needed,
            suggested_order_qty=round_qty(suggested_qty),
            estimated_cost=estimated_cost,
            data_quality=data_quality,
        )

        evidence = EvidenceMetadata(
            source_record_ids=[item.id for item in sale_items],
            date_window_start=since_date,
            date_window_end=datetime.now(UTC),
            calculation_method="rolling_mean_baseline_forecast",
            assumptions=[
                f"Demand estimated from {history_days}-day rolling average sales",
                f"Lead time assumed = {lead_time_days} days",
                f"Order rounded to pack size {pack_size} and MOQ {moq}",
            ],
            freshness_timestamp=datetime.now(UTC),
            warnings=[]
            if data_quality == "RELIABLE"
            else ["Sparse sales history; forecast uncertainty is high."],
        )

        return DomainResult(data=result, evidence=evidence)
