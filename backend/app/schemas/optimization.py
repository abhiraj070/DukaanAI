"""Typed schemas for Budget-Constrained Procurement and Profit Optimization."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OptimizationInput(BaseModel):
    """Input parameters for procurement optimization.

    Principles:
    - Never exceeds stated procurement budget.
    - Receivables are not cash by default.
    - Respects supplier MOQ and pack size.
    """

    model_config = ConfigDict(frozen=True)

    budget_inr: Decimal = Field(
        ..., gt=Decimal("0.00"), description="Available cash procurement budget (INR)"
    )
    planning_horizon_days: int = Field(default=14, ge=1, le=90)
    category_id: str | None = None
    include_receivables: bool = Field(
        default=False,
        description="Whether to count expected customer receivables as cash (Default: False)",
    )


class ProcurementItemRecommendation(BaseModel):
    """Specific SKU replenishment recommendation."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    product_name: str
    sku: str | None = None
    supplier_name: str | None = None
    unit: str
    current_stock: Decimal
    daily_demand: Decimal
    order_quantity: Decimal = Field(
        ..., description="Recommended order quantity, rounded to supplier pack size and MOQ"
    )
    unit_cost: Decimal
    total_cost: Decimal
    expected_selling_price: Decimal
    expected_revenue: Decimal
    expected_gross_profit: Decimal
    target_coverage_days: int
    moq_applied: Decimal
    pack_size_applied: Decimal


class OptimizationResult(BaseModel):
    """Budget-constrained procurement optimization output."""

    model_config = ConfigDict(frozen=True)

    budget_allocated: Decimal = Field(..., description="Total procurement spend recommended (INR)")
    budget_remaining: Decimal = Field(..., description="Unspent budget remainder (INR)")
    total_expected_revenue: Decimal
    total_expected_gross_profit: Decimal
    roi_pct: Decimal
    recommendations: list[ProcurementItemRecommendation]
    objective: str = "maximize expected gross contribution under budget and supplier constraints"
    method: str = "discrete_knapsack_with_moq_and_pack_size"
