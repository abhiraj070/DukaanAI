"""Base tenant-scoped repository enforcing strict business isolation."""

from typing import TypeVar

from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.core.errors import ForbiddenError, NotFoundError
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseTenantRepository[ModelType: Base]:
    """Base repository where every query, mutation, and deletion is strictly
    scoped to the authenticated business_id.
    """

    def __init__(self, db: Session, context_or_business_id: BusinessContext | str) -> None:
        self.db = db
        if isinstance(context_or_business_id, BusinessContext):
            self.business_id = context_or_business_id.business_id
            self.user_id = context_or_business_id.user_id
        else:
            self.business_id = context_or_business_id
            self.user_id = None

    @property
    def model(self) -> type[ModelType]:
        """Subclasses must define the target SQLAlchemy model."""
        raise NotImplementedError

    def _base_query(self):
        """Construct a query with mandatory business_id predicate."""
        return self.db.query(self.model).filter(self.model.business_id == self.business_id)

    def get_by_id(self, entity_id: str) -> ModelType | None:
        """Fetch a single entity by ID strictly within the tenant boundary."""
        return self._base_query().filter(self.model.id == entity_id).first()

    def get_by_id_or_fail(
        self, entity_id: str, error_message: str = "Resource not found"
    ) -> ModelType:
        """Fetch entity by ID or raise NotFoundError."""
        entity = self.get_by_id(entity_id)
        if not entity:
            raise NotFoundError(error_message)
        return entity

    def list_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """List entities for this business with pagination."""
        return self._base_query().offset(skip).limit(limit).all()

    def count(self) -> int:
        """Count total entities belonging to this business."""
        return self._base_query().count()

    def save(self, entity: ModelType) -> ModelType:
        """Persist entity ensuring business_id matches tenant context."""
        if hasattr(entity, "business_id"):
            if entity.business_id and entity.business_id != self.business_id:
                raise ForbiddenError("Attempt to write entity across tenant boundary")
            entity.business_id = self.business_id

        self.db.add(entity)
        self.db.flush()
        return entity

    def delete(self, entity_id: str) -> bool:
        """Delete an entity strictly within tenant boundary."""
        entity = self.get_by_id(entity_id)
        if not entity:
            return False
        self.db.delete(entity)
        self.db.flush()
        return True
