"""Typed schemas for Inventory Intelligence and Demand Forecasting."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InventoryStatusItem(BaseModel):
    """Authoritative physical stock status for a product."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    name: str
    sku: str | None = None
    unit: str
    selling_price: Decimal
    cost_price: Decimal | None = None
    on_hand_stock: Decimal = Field(
        ..., description="Authoritative stock level reconciled from movements"
    )
    min_stock_level: Decimal
    reorder_quantity: Decimal
    is_low_stock: bool
    is_stockout: bool


class DemandForecastResult(BaseModel):
    """Demand forecast and reorder recommendations.

    Formulas:
    Days of cover = current usable stock / average daily demand
    ROP = (forecast daily demand * lead_time_days) + safety_stock
    """

    model_config = ConfigDict(frozen=True)

    product_id: str
    product_name: str
    sku: str | None = None
    unit: str
    on_hand_stock: Decimal
    incoming_stock: Decimal = Decimal("0.000")
    historical_daily_demand: Decimal
    horizon_days: int
    forecast_demand_period: Decimal
    days_of_cover: Decimal | None = Field(
        default=None,
        description="Days until stock is exhausted; None if daily demand is zero",
    )
    supplier_lead_time_days: int
    safety_stock: Decimal
    reorder_point: Decimal = Field(
        ..., description="ROP = (daily demand * lead time) + safety stock"
    )
    is_reorder_recommended: bool
    suggested_order_qty: Decimal = Field(
        ..., description="Suggested replenishment quantity respecting MOQ and pack size"
    )
    estimated_cost: Decimal | None = None
    data_quality: str = Field(..., description="'RELIABLE', 'SPARSE', or 'NO_HISTORY'")
    forecast_method: str = "rolling_mean"
    training_window_days: int = 30
    model_version: str = "inventory_forecast_v2"


class StoreInventorySummary(BaseModel):
    """Aggregated store inventory valuation and health metrics."""

    model_config = ConfigDict(frozen=True)

    total_products_count: int
    low_stock_products_count: int
    stockout_products_count: int
    total_inventory_valuation: Decimal | None = Field(
        default=None,
        description="Total valuation at cost price; None if cost data is incomplete",
    )
    products: list[InventoryStatusItem]
