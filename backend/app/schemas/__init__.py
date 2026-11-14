"""DukaanAI typed contracts and schema package."""

from app.schemas.analytics import (
    AnalyticsFilter,
    KPIOverview,
    ProductPerformanceItem,
    ProductRankingResponse,
)
from app.schemas.common import DomainResult, EvidenceMetadata, round_curr, round_qty
from app.schemas.inventory import (
    DemandForecastResult,
    InventoryStatusItem,
    StoreInventorySummary,
)
from app.schemas.optimization import (
    OptimizationInput,
    OptimizationResult,
    ProcurementItemRecommendation,
)
from app.schemas.simulation import (
    ScenarioItemInput,
    SimulationInput,
    SimulationMetricDelta,
    SimulationResult,
)
from app.schemas.udhar import (
    AgingBucket,
    CustomerStatement,
    StatementLineItem,
    UdharSummary,
)

__all__ = [
    "DomainResult",
    "EvidenceMetadata",
    "round_curr",
    "round_qty",
    "AnalyticsFilter",
    "KPIOverview",
    "ProductPerformanceItem",
    "ProductRankingResponse",
    "InventoryStatusItem",
    "DemandForecastResult",
    "StoreInventorySummary",
    "AgingBucket",
    "UdharSummary",
    "StatementLineItem",
    "CustomerStatement",
    "ScenarioItemInput",
    "SimulationInput",
    "SimulationMetricDelta",
    "SimulationResult",
    "OptimizationInput",
    "OptimizationResult",
    "ProcurementItemRecommendation",
]
