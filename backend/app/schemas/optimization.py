"""Typed schemas for Budget-Constrained Procurement and Profit Optimization."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    @model_validator(mode="after")
    def receivables_are_not_procurement_cash(self):
        if self.include_receivables:
            raise ValueError("Receivables cannot be counted as procurement cash")
        return self


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
    moq_applied: Decimal | None = None
    pack_size_applied: Decimal | None = None
    expected_units_sold: Decimal = Decimal("0.000")
    incoming_stock: Decimal = Decimal("0.000")


class OptimizationAlternative(BaseModel):
    model_config = ConfigDict(frozen=True)

    recommendation: ProcurementItemRecommendation
    reason_not_selected: str


class OptimizationResult(BaseModel):
    """Budget-constrained procurement optimization output."""

    model_config = ConfigDict(frozen=True)

    budget_allocated: Decimal = Field(..., description="Total procurement spend recommended (INR)")
    budget_remaining: Decimal = Field(..., description="Unspent budget remainder (INR)")
    total_expected_revenue: Decimal
    total_expected_gross_profit: Decimal
    roi_pct: Decimal
    recommendations: list[ProcurementItemRecommendation]
    alternatives: list[OptimizationAlternative] = Field(default_factory=list)
    explanation: str = (
        "Ranks feasible replenishment candidates by expected gross contribution "
        "per rupee under the stated budget."
    )
    warnings: list[str] = Field(default_factory=list)
    objective: str = "maximize expected gross contribution under budget and supplier constraints"
    method: str = "discrete_knapsack_with_moq_and_pack_size"
