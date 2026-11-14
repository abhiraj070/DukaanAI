"""SQLAlchemy declarative base and metadata definitions."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Strict naming convention for foreign keys, primary keys, indexes, and unique constraints
# to ensure reproducible and deterministic Alembic migrations.
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base model class with common id and timestamp helpers."""

    metadata = metadata

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance attributes to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


def generate_uuid() -> str:
    """Generate a 32-character hexadecimal UUID string."""
    return uuid.uuid4().hex


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)
