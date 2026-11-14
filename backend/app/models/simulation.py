"""Tenant-scoped saved what-if scenario runs."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, generate_uuid, utc_now


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_name: Mapped[str] = mapped_column(String(160), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    __table_args__ = (Index("ix_scenario_business_created", "business_id", "created_at"),)
