"""Tenant-scoped festival calendar and evidence-based uplift service."""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.core.errors import BadRequestError, NotFoundError
from app.models.catalogue import Category, Product
from app.models.festival import FestivalCalendarEvent
from app.models.operations import Sale, SaleItem
from app.schemas.common import DomainResult, EvidenceMetadata, round_curr, round_qty
from app.schemas.festivals import FestivalEventInput, FestivalUpliftResult


class FestivalIntelligenceService:
    def __init__(self, db: Session, context: BusinessContext) -> None:
        self.db = db
        self.context = context
        self.business_id = context.business_id

    def list_events(self) -> list[FestivalCalendarEvent]:
        return (
            self.db.query(FestivalCalendarEvent)
            .filter(FestivalCalendarEvent.business_id == self.business_id)
            .order_by(FestivalCalendarEvent.start_date)
            .all()
        )

    def save_event(
        self, payload: FestivalEventInput, event_id: str | None = None
    ) -> FestivalCalendarEvent:
        event = None
        if event_id:
            event = (
                self.db.query(FestivalCalendarEvent)
                .filter(
                    FestivalCalendarEvent.id == event_id,
                    FestivalCalendarEvent.business_id == self.business_id,
                )
                .first()
            )
            if not event:
                raise NotFoundError("Festival event not found in this business")
        if (
            payload.category_id
            and not self.db.query(Category.id)
            .filter(Category.id == payload.category_id, Category.business_id == self.business_id)
            .first()
        ):
            raise BadRequestError("Category does not belong to this business")
        if event is None:
            event = FestivalCalendarEvent(business_id=self.business_id, source="USER")
            self.db.add(event)
        for field, value in payload.model_dump().items():
            setattr(event, field, value)
        self.db.commit()
        self.db.refresh(event)
        return event

    def estimate_uplift(
        self, event_id: str, assumed_uplift_pct: Decimal | None = None
    ) -> DomainResult[FestivalUpliftResult]:
        event = (
            self.db.query(FestivalCalendarEvent)
            .filter(
                FestivalCalendarEvent.id == event_id,
                FestivalCalendarEvent.business_id == self.business_id,
            )
            .first()
        )
        if not event:
            raise NotFoundError("Festival event not found in this business")
        past_events = (
            self.db.query(FestivalCalendarEvent)
            .filter(
                FestivalCalendarEvent.business_id == self.business_id,
                FestivalCalendarEvent.name == event.name,
                FestivalCalendarEvent.region == event.region,
                FestivalCalendarEvent.category_id == event.category_id,
                FestivalCalendarEvent.end_date < event.start_date,
                FestivalCalendarEvent.id != event.id,
            )
            .order_by(FestivalCalendarEvent.start_date.desc())
            .limit(5)
            .all()
        )
        uplifts: list[Decimal] = []
        baseline_units: list[Decimal] = []
        festival_units: list[Decimal] = []
        source_ids: list[str] = [event.id]
        for past in past_events:
            baseline_start = past.start_date - timedelta(days=28)
            start_dt = datetime.combine(baseline_start, time.min, tzinfo=UTC)
            festival_start = datetime.combine(past.start_date, time.min, tzinfo=UTC)
            festival_end = datetime.combine(past.end_date + timedelta(days=1), time.min, tzinfo=UTC)
            base_q = self._sales_query(start_dt, festival_start, event.category_id)
            fest_q = self._sales_query(festival_start, festival_end, event.category_id)
            base_rows, fest_rows = base_q.all(), fest_q.all()
            if len(base_rows) < 5 or len(fest_rows) < 5:
                continue
            base_total = sum((row.quantity for row in base_rows), start=Decimal("0.000"))
            fest_total = sum((row.quantity for row in fest_rows), start=Decimal("0.000"))
            base_daily = base_total / Decimal("28")
            fest_daily = fest_total / Decimal(str((past.end_date - past.start_date).days + 1))
            if base_daily <= 0:
                continue
            uplifts.append((fest_daily / base_daily - Decimal("1")) * Decimal("100"))
            baseline_units.append(base_daily)
            festival_units.append(fest_daily)
            source_ids.extend(row.id for row in base_rows + fest_rows)

        observed = (
            sum(uplifts, start=Decimal("0")) / Decimal(str(len(uplifts)))
            if len(uplifts) >= 2
            else None
        )
        quality = (
            "HISTORICAL"
            if observed is not None
            else ("USER_ASSUMPTION" if assumed_uplift_pct is not None else "INSUFFICIENT_HISTORY")
        )
        planning = observed if observed is not None else assumed_uplift_pct
        assumptions = [
            "Observed uplift compares matched occurrences with the preceding 28-day baseline.",
            "Historical estimate requires two occurrences and five sale lines in both windows.",
        ]
        if quality == "USER_ASSUMPTION":
            assumptions.append(
                f"Planning uplift uses user-provided assumption: {assumed_uplift_pct}%."
            )
        warnings = (
            []
            if observed is not None
            else ["Insufficient history; planning uplift is a user assumption."]
        )
        result = FestivalUpliftResult(
            event_id=event.id,
            event_name=event.name,
            observed_uplift_pct=round_curr(observed),
            planning_uplift_pct=round_curr(planning),
            quality=quality,
            comparable_occurrences=len(uplifts),
            baseline_daily_units=round_qty(
                sum(baseline_units, start=Decimal("0")) / Decimal(str(len(baseline_units)))
            )
            if baseline_units
            else None,
            festival_daily_units=round_qty(
                sum(festival_units, start=Decimal("0")) / Decimal(str(len(festival_units)))
            )
            if festival_units
            else None,
            assumptions=assumptions,
            warnings=warnings,
        )
        evidence = EvidenceMetadata(
            source_record_ids=source_ids[:100],
            date_window_start=datetime.combine(event.start_date, time.min, tzinfo=UTC),
            date_window_end=datetime.combine(
                event.end_date + timedelta(days=1), time.min, tzinfo=UTC
            ),
            calculation_method="matched_festival_occurrence_vs_preceding_28_day_baseline",
            assumptions=assumptions,
            warnings=warnings,
        )
        return DomainResult(data=result, evidence=evidence)

    def _sales_query(self, start: datetime, end: datetime, category_id: str | None):
        query = (
            self.db.query(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .filter(
                SaleItem.business_id == self.business_id,
                Sale.status == "COMPLETED",
                Sale.sold_at >= start,
                Sale.sold_at < end,
            )
        )
        if category_id:
            query = query.join(Product, SaleItem.product_id == Product.id).filter(
                Product.business_id == self.business_id, Product.category_id == category_id
            )
        return query
