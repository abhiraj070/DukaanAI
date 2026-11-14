"""Common typed schemas, evidence metadata envelopes, and Decimal helpers."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


def round_curr(val: Decimal | None) -> Decimal | None:
    """Round monetary Decimal to 2 decimal places using standard financial half-up."""
    if val is None:
        return None
    return val.quantize(Decimal("0.01"))


def round_qty(val: Decimal | None) -> Decimal | None:
    """Round physical quantity Decimal to 3 decimal places."""
    if val is None:
        return None
    return val.quantize(Decimal("0.001"))


class EvidenceMetadata(BaseModel):
    """Standard evidence metadata envelope for all deterministic calculation results.

    Provides complete transparency into data provenance, time window, calculation
    methodology, assumptions, and quality warnings.
    """

    model_config = ConfigDict(frozen=True)

    source_record_ids: list[str] = Field(
        default_factory=list,
        description="IDs of primary source records (sales, movements, transactions) used",
    )
    date_window_start: datetime | None = Field(
        default=None, description="Start boundary of analysis window (UTC)"
    )
    date_window_end: datetime | None = Field(
        default=None, description="End boundary of analysis window (UTC)"
    )
    calculation_method: str = Field(..., description="Exact algorithm or methodology applied")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions made (e.g. constant lead time, collection estimates)",
    )
    freshness_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when calculations were performed",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Data quality warnings (e.g. missing product cost, sparse history)",
    )


class DomainResult[T](BaseModel):
    """Standard envelope wrapping domain service outputs with evidence metadata."""

    model_config = ConfigDict(frozen=True)

    data: T
    evidence: EvidenceMetadata
