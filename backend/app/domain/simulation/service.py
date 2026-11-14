"""Deterministic What-if Decision Simulation Domain Service."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.core.errors import BadRequestError
from app.domain.festivals.service import FestivalIntelligenceService
from app.models.catalogue import Product
from app.models.operations import Sale, SaleItem
from app.models.simulation import ScenarioRun
from app.schemas.common import DomainResult, EvidenceMetadata, round_curr
from app.schemas.simulation import (
    SimulationInput,
    SimulationMetricDelta,
    SimulationResult,
)


class SimulationService:
    """Service providing deterministic What-if business scenario simulations.

    Principles:
    - Do not assume demand remains constant after price changes without explicit user assumptions.
    - Expected collections are estimates, not guaranteed cash.
    - Full transparency into assumptions, deltas, and model version.
    """

    def __init__(self, db: Session, context: BusinessContext) -> None:
        self.db = db
        self.context = context
        self.business_id = context.business_id

    def run_scenario(self, input_data: SimulationInput) -> DomainResult[SimulationResult]:
        """Execute a deterministic scenario projection against historical business baselines."""
        horizon = input_data.time_horizon_days
        history_window = 30  # 30-day baseline window

        since_date = datetime.now(UTC) - timedelta(days=history_window)
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

        # Baseline product aggregation (daily average)
        daily_baseline: dict[str, dict] = {}
        for item in sale_items:
            if item.product_id not in daily_baseline:
                daily_baseline[item.product_id] = {
                    "product": item.product,
                    "units": Decimal("0.000"),
                    "revenue": Decimal("0.00"),
                    "cogs": Decimal("0.00") if item.unit_cost is not None else None,
                }
            entry = daily_baseline[item.product_id]
            entry["units"] += item.quantity / Decimal(str(history_window))
            entry["revenue"] += item.total_amount / Decimal(str(history_window))
            if entry["cogs"] is not None and item.unit_cost is not None:
                entry["cogs"] += (item.quantity * item.unit_cost) / Decimal(str(history_window))
            else:
                entry["cogs"] = None

        # Build baseline projected over horizon
        baseline_rev = sum(
            (d["revenue"] * Decimal(str(horizon)) for d in daily_baseline.values()),
            start=Decimal("0.00"),
        )
        has_missing_cogs = any(d["cogs"] is None for d in daily_baseline.values())
        baseline_cogs = (
            sum(
                (
                    d["cogs"] * Decimal(str(horizon))
                    for d in daily_baseline.values()
                    if d["cogs"] is not None
                ),
                start=Decimal("0.00"),
            )
            if not has_missing_cogs
            else None
        )
        baseline_profit = (baseline_rev - baseline_cogs) if baseline_cogs is not None else None

        # Map item overrides
        item_overrides = {item.product_id: item for item in input_data.items}
        valid_product_ids = {
            product_id
            for (product_id,) in self.db.query(Product.id)
            .filter(Product.business_id == self.business_id)
            .all()
        }
        if set(item_overrides) - valid_product_ids:
            raise BadRequestError("Scenario includes a product outside the current business")

        simulated_rev = Decimal("0.00")
        simulated_cogs = Decimal("0.00") if not has_missing_cogs else None

        festival_source_ids: list[str] = []
        festival_assumptions: list[str] = []
        festival_multiplier = Decimal("1.00")
        if input_data.festival_event_id:
            festival_result = FestivalIntelligenceService(self.db, self.context).estimate_uplift(
                input_data.festival_event_id, input_data.festival_assumed_uplift_pct
            )
            if festival_result.data.planning_uplift_pct is None:
                raise BadRequestError(
                    "Festival history is insufficient; provide festival_assumed_uplift_pct."
                )
            festival_multiplier += festival_result.data.planning_uplift_pct / Decimal("100")
            festival_source_ids.extend(festival_result.evidence.source_record_ids)
            festival_assumptions.extend(festival_result.data.assumptions)

        general_demand_mult = (
            Decimal("1.00") + input_data.general_demand_uplift_pct / Decimal("100.0")
        ) * festival_multiplier

        for pid, d in daily_baseline.items():
            p: Product = d["product"]
            override = item_overrides.get(pid)

            # Price modifier
            price_mult = Decimal("1.00")
            if override and override.price_delta_pct is not None:
                price_mult += override.price_delta_pct / Decimal("100.0")

            # Cost modifier
            cost_mult = Decimal("1.00")
            if override and override.cost_delta_pct is not None:
                cost_mult += override.cost_delta_pct / Decimal("100.0")

            # Demand modifier
            demand_mult = general_demand_mult
            if override and override.demand_delta_pct is not None:
                demand_mult *= Decimal("1.00") + (override.demand_delta_pct / Decimal("100.0"))

            sim_item_units = d["units"] * Decimal(str(horizon)) * demand_mult
            sim_item_price = p.selling_price * price_mult
            simulated_rev += sim_item_units * sim_item_price

            if simulated_cogs is not None and p.cost_price is not None:
                sim_item_cost = p.cost_price * cost_mult
                simulated_cogs += sim_item_units * sim_item_cost

        simulated_profit = (simulated_rev - simulated_cogs) if simulated_cogs is not None else None

        def calc_delta(base: Decimal | None, sim: Decimal | None) -> SimulationMetricDelta | None:
            if base is None or sim is None:
                return None
            delta_amt = round_curr(sim - base)
            delta_pct = (
                round_curr((delta_amt / base) * Decimal("100.0")) if base > Decimal("0") else None
            )
            return SimulationMetricDelta(
                baseline=round_curr(base),
                simulated=round_curr(sim),
                delta_amount=delta_amt,
                delta_pct=delta_pct,
            )

        rev_delta = calc_delta(baseline_rev, simulated_rev)
        cogs_delta = calc_delta(baseline_cogs, simulated_cogs)
        profit_delta = calc_delta(baseline_profit, simulated_profit)

        assumptions = [
            f"Baseline demand extrapolated from {history_window}-day historical sales",
            (
                "Price elasticity assumed = 0 "
                "(demand volume is independent of price changes unless specified)"
            ),
            (
                f"Expected udhar collections (₹{input_data.expected_udhar_collections}) "
                "are scenario inputs, not guaranteed cash"
            ),
        ] + festival_assumptions
        risks = []
        if input_data.purchase_cash_outflow:
            assumptions.append(
                "Purchase cash outflow is kept separate from gross profit and receivables."
            )
        if input_data.supply_delay_days:
            risks.append(
                "Supply delay is recorded as an assumption; "
                "purchase order availability is not modeled."
            )

        if has_missing_cogs:
            risks.append(
                "Missing cost prices on some historical products; profit projections unavailable."
            )

        result = SimulationResult(
            scenario_name=input_data.scenario_name,
            time_horizon_days=horizon,
            revenue=rev_delta,  # type: ignore
            cogs=cogs_delta,
            gross_profit=profit_delta,
            cash_collected_estimate=round_curr(input_data.expected_udhar_collections),
            purchase_cash_outflow=round_curr(input_data.purchase_cash_outflow),
            supply_delay_days=input_data.supply_delay_days,
            assumptions_applied=assumptions,
            constraints_and_risks=risks,
        )

        evidence = EvidenceMetadata(
            source_record_ids=([item.id for item in sale_items[:50]] + festival_source_ids)[:100],
            date_window_start=since_date,
            date_window_end=datetime.now(UTC),
            calculation_method="deterministic_what_if_scenario_modeling",
            assumptions=assumptions,
            freshness_timestamp=datetime.now(UTC),
            warnings=risks,
        )

        run = ScenarioRun(
            business_id=self.business_id,
            scenario_name=input_data.scenario_name,
            model_version=result.model_version,
            input_json=input_data.model_dump(mode="json"),
            result_json=result.model_dump(mode="json"),
            evidence_json=evidence.model_dump(mode="json"),
        )
        self.db.add(run)
        self.db.commit()

        return DomainResult(data=result, evidence=evidence)

    def list_scenarios(self, limit: int = 20) -> list[dict]:
        runs = (
            self.db.query(ScenarioRun)
            .filter(ScenarioRun.business_id == self.business_id)
            .order_by(ScenarioRun.created_at.desc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
        return [
            {
                "id": r.id,
                "scenario_name": r.scenario_name,
                "model_version": r.model_version,
                "created_at": r.created_at.isoformat(),
                "input": r.input_json,
                "result": r.result_json,
                "evidence": r.evidence_json,
            }
            for r in runs
        ]
