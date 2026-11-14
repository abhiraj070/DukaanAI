"""Typed schemas for What-if Decision Simulation."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScenarioItemInput(BaseModel):
    """Specific SKU overrides for a scenario."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    price_delta_pct: Decimal | None = Field(
        default=None, description="Percentage change in price (e.g. +10.0 for 10% increase)"
    )
    cost_delta_pct: Decimal | None = Field(
        default=None, description="Percentage change in supplier cost (e.g. -5.0 for 5% decrease)"
    )
    demand_delta_pct: Decimal | None = Field(
        default=None,
        description="Explicit assumed demand change (e.g. +20.0 for 20% surge)",
    )

    @model_validator(mode="after")
    def validate_item(self):
        if self.price_delta_pct is not None and self.price_delta_pct <= -100:
            raise ValueError("Price decrease cannot reach or exceed -100%")
        return self


class SimulationInput(BaseModel):
    """Parameters for running a deterministic What-if scenario.

    Principles:
    - Never assume price elasticity without explicit user assumption.
    - Expected collections are estimates, not guaranteed cash.
    """

    model_config = ConfigDict(frozen=True)

    scenario_name: str
    time_horizon_days: int = Field(default=30, ge=1, le=365)
    general_demand_uplift_pct: Decimal = Field(
        default=Decimal("0.00"), description="Store-wide demand change percentage"
    )
    items: list[ScenarioItemInput] = Field(default_factory=list)
    expected_udhar_collections: Decimal = Field(
        default=Decimal("0.00"), description="Hypothetical collection of outstanding udhar (INR)"
    )
    purchase_cash_outflow: Decimal = Field(default=Decimal("0.00"), ge=0)
    supply_delay_days: int = Field(default=0, ge=0, le=365)
    festival_event_id: str | None = None
    festival_assumed_uplift_pct: Decimal | None = Field(
        default=None, ge=Decimal("-100"), le=Decimal("1000")
    )

    @model_validator(mode="after")
    def validate_scenario(self):
        if not self.scenario_name.strip():
            raise ValueError("scenario_name cannot be blank")
        if self.general_demand_uplift_pct <= -100 or self.expected_udhar_collections < 0:
            raise ValueError("Demand change must exceed -100% and collections cannot be negative")
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate product override in scenario")
        return self


class SimulationMetricDelta(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline: Decimal
    simulated: Decimal
    delta_amount: Decimal
    delta_pct: Decimal | None = None


class SimulationResult(BaseModel):
    """Result of running a What-if scenario comparison against baseline."""

    model_config = ConfigDict(frozen=True)

    scenario_name: str
    time_horizon_days: int
    revenue: SimulationMetricDelta
    cogs: SimulationMetricDelta | None = None
    gross_profit: SimulationMetricDelta | None = None
    cash_collected_estimate: Decimal
    purchase_cash_outflow: Decimal = Decimal("0.00")
    supply_delay_days: int = 0
    assumptions_applied: list[str]
    constraints_and_risks: list[str]
    model_version: str = "what_if_v1"
