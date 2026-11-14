"""Deterministic Budget-Constrained Procurement Optimization Domain Service."""

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.models.catalogue import Product, SupplierProduct
from app.models.operations import Sale, SaleItem
from app.repositories.inventory import InventoryRepository
from app.schemas.common import DomainResult, EvidenceMetadata, round_curr, round_qty
from app.schemas.optimization import (
    OptimizationInput,
    OptimizationResult,
    ProcurementItemRecommendation,
)


class ProcurementOptimizerService:
    """Service providing budget-constrained procurement allocation recommendations.

    Principles:
    - Never exceeds the user's allocated procurement budget.
    - Receivables are not cash by default.
    - Recommends order quantities respecting supplier MOQ and pack size.
    """

    def __init__(self, db: Session, context: BusinessContext) -> None:
        self.db = db
        self.context = context
        self.business_id = context.business_id
        self.inv_repo = InventoryRepository(db, context)

    def optimize_procurement(
        self, input_data: OptimizationInput
    ) -> DomainResult[OptimizationResult]:
        """Compute replenishment recommendations under a strict budget constraint."""
        budget = input_data.budget_inr
        horizon = input_data.planning_horizon_days
        history_days = 30

        products_q = self.db.query(Product).filter(
            Product.business_id == self.business_id,
            Product.is_active.is_(True),
        )
        if input_data.category_id:
            products_q = products_q.filter(Product.category_id == input_data.category_id)

        products = products_q.all()

        since_date = datetime.now(UTC) - timedelta(days=history_days)
        sale_items = (
            self.db.query(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .filter(
                SaleItem.business_id == self.business_id,
                Sale.sold_at >= since_date,
                Sale.status == "COMPLETED",
            )
            .all()
        )

        # Calculate daily demand per product
        demand_map: dict[str, Decimal] = {}
        for item in sale_items:
            demand_map[item.product_id] = demand_map.get(item.product_id, Decimal("0.000")) + (
                item.quantity / Decimal(str(history_days))
            )

        candidates: list[dict] = []

        for p in products:
            daily_demand = demand_map.get(p.id, Decimal("0.000"))
            current_stock = self.inv_repo.get_stock(p.id)

            # Check supplier specifications
            supp_link = (
                self.db.query(SupplierProduct)
                .filter(
                    SupplierProduct.business_id == self.business_id,
                    SupplierProduct.product_id == p.id,
                )
                .first()
            )

            unit_cost = supp_link.purchase_cost if supp_link else p.cost_price
            moq = supp_link.moq if supp_link else Decimal("1.000")
            pack_size = supp_link.pack_size if supp_link else Decimal("1.000")

            if unit_cost is None or unit_cost <= Decimal("0.00") or p.selling_price <= unit_cost:
                continue  # Skip items with missing or unprofitable cost

            # Needed stock over horizon + safety stock
            target_stock = (daily_demand * Decimal(str(horizon))) + p.min_stock_level
            net_need = target_stock - current_stock

            if net_need <= Decimal("0.000"):
                continue  # Stock is already sufficient

            # Round to supplier pack size and MOQ
            order_qty = net_need if net_need >= moq else moq
            if pack_size > Decimal("0"):
                mult = math.ceil(float(order_qty) / float(pack_size))
                order_qty = Decimal(str(mult)) * pack_size

            total_cost = order_qty * unit_cost
            expected_rev = order_qty * p.selling_price
            expected_profit = expected_rev - total_cost

            roi = expected_profit / total_cost if total_cost > Decimal("0") else Decimal("0")

            candidates.append(
                {
                    "product": p,
                    "supplier_name": p.supplier.name if p.supplier else None,
                    "current_stock": current_stock,
                    "daily_demand": daily_demand,
                    "order_qty": order_qty,
                    "unit_cost": unit_cost,
                    "total_cost": total_cost,
                    "expected_rev": expected_rev,
                    "expected_profit": expected_profit,
                    "roi": roi,
                    "moq": moq,
                    "pack_size": pack_size,
                }
            )

        # Sort by ROI descending (highest return on budget first)
        candidates.sort(key=lambda x: x["roi"], reverse=True)

        recommendations: list[ProcurementItemRecommendation] = []
        budget_remaining = budget
        total_allocated = Decimal("0.00")
        total_rev = Decimal("0.00")
        total_profit = Decimal("0.00")

        for c in candidates:
            cost = c["total_cost"]
            if budget_remaining >= cost:
                budget_remaining -= cost
                total_allocated += cost
                total_rev += c["expected_rev"]
                total_profit += c["expected_profit"]

                recommendations.append(
                    ProcurementItemRecommendation(
                        product_id=c["product"].id,
                        product_name=c["product"].name,
                        sku=c["product"].sku,
                        supplier_name=c["supplier_name"],
                        unit=c["product"].unit,
                        current_stock=round_qty(c["current_stock"]),
                        daily_demand=round_qty(c["daily_demand"]),
                        order_quantity=round_qty(c["order_qty"]),
                        unit_cost=round_curr(c["unit_cost"]),
                        total_cost=round_curr(cost),
                        expected_selling_price=round_curr(c["product"].selling_price),
                        expected_revenue=round_curr(c["expected_rev"]),
                        expected_gross_profit=round_curr(c["expected_profit"]),
                        target_coverage_days=horizon,
                        moq_applied=round_qty(c["moq"]),
                        pack_size_applied=round_qty(c["pack_size"]),
                    )
                )

        roi_pct = (
            round_curr((total_profit / total_allocated) * Decimal("100.0"))
            if total_allocated > Decimal("0")
            else Decimal("0.00")
        )

        result = OptimizationResult(
            budget_allocated=round_curr(total_allocated),
            budget_remaining=round_curr(budget_remaining),
            total_expected_revenue=round_curr(total_rev),
            total_expected_gross_profit=round_curr(total_profit),
            roi_pct=roi_pct,
            recommendations=recommendations,
        )

        evidence = EvidenceMetadata(
            source_record_ids=[c["product"].id for c in candidates],
            date_window_start=since_date,
            date_window_end=datetime.now(UTC),
            calculation_method="roi_ranked_greedy_knapsack_with_moq_pack_size",
            assumptions=[
                f"Budget constraint: ₹{budget}",
                f"Coverage horizon: {horizon} days",
                "Receivables excluded from cash unless specified",
            ],
            freshness_timestamp=datetime.now(UTC),
            warnings=[]
            if recommendations
            else ["Budget insufficient to satisfy minimum supplier MOQ constraints."],
        )

        return DomainResult(data=result, evidence=evidence)
