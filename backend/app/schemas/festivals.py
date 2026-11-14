"""Typed contracts for festival calendar and seasonal demand evidence."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FestivalEventInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = Field(min_length=1, max_length=160)
    region: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
    category_id: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def dates_are_ordered(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class FestivalEventResponse(FestivalEventInput):
    model_config = ConfigDict(from_attributes=True, frozen=True)
    id: str
    source: str


class FestivalUpliftInput(BaseModel):
    assumed_uplift_pct: Decimal | None = Field(default=None, ge=Decimal("-100"), le=Decimal("1000"))


class FestivalUpliftResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    event_name: str
    observed_uplift_pct: Decimal | None = None
    planning_uplift_pct: Decimal | None = None
    quality: str
    comparable_occurrences: int
    baseline_daily_units: Decimal | None = None
    festival_daily_units: Decimal | None = None
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
