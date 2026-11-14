"""Typed schemas for What-if Decision Simulation Engine."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ScenarioItemInput(BaseModel):
    """Product-level scenario adjustment parameters."""

    product_id: str
    price_delta_pct: Decimal | None = Field(
        default=None, description="Percentage change in selling price (e.g. +5.0 or -10.0)"
    )
    cost_delta_pct: Decimal | None = Field(
        default=None, description="Percentage change in supplier cost price"
    )
    demand_delta_pct: Decimal | None = Field(
        default=None, description="User-assumed demand volume change percentage"
    )


class SimulationInput(BaseModel):
    """What-if scenario simulation request.

    Principles:
    - Never assume demand elasticity without explicit user assumption.
    - Expected udhar collections are scenario inputs, not guaranteed cash.
    """

    model_config = ConfigDict(frozen=True)

    scenario_name: str
    time_horizon_days: int = Field(default=30, ge=1, le=365)
    items: list[ScenarioItemInput] = Field(default_factory=list)
    general_demand_uplift_pct: Decimal = Field(
        default=Decimal("0.00"),
        description="General store demand uplift assumption (e.g. festival +15%)",
    )
    expected_udhar_collections: Decimal = Field(
        default=Decimal("0.00"), description="Hypothetical collection of outstanding udhar (INR)"
    )


class SimulationMetricDelta(BaseModel):
    """Comparison between observed baseline and simulated scenario."""

    baseline: Decimal
    simulated: Decimal
    delta_amount: Decimal
    delta_pct: Decimal | None = None


class SimulationResult(BaseModel):
    """Deterministic scenario simulation output."""

    model_config = ConfigDict(frozen=True)

    scenario_name: str
    time_horizon_days: int
    revenue: SimulationMetricDelta
    cogs: SimulationMetricDelta | None = None
    gross_profit: SimulationMetricDelta | None = None
    cash_collected_estimate: Decimal
    assumptions_applied: list[str]
    constraints_and_risks: list[str]
    model_version: str = "sim_v1.0_deterministic"
