"""Tenant-scoped repository for Inventory Movements and Stock Reconciliation."""

from decimal import Decimal

from app.core.errors import BadRequestError, NotFoundError
from app.models.catalogue import Product
from app.models.inventory import InventoryMovement, MovementType
from app.repositories.base import BaseTenantRepository


class InventoryRepository(BaseTenantRepository[InventoryMovement]):
    """Tenant-scoped Inventory Movement repository."""

    @property
    def model(self) -> type[InventoryMovement]:
        return InventoryMovement

    def record_movement(
        self,
        product_id: str,
        movement_type: MovementType | str,
        quantity: Decimal,
        unit_cost: Decimal | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        notes: str | None = None,
        created_by: str | None = None,
    ) -> InventoryMovement:
        """Record an immutable inventory movement.

        Enforces:
        - Product must belong to this tenant.
        - Quantity must be strictly positive Decimal.
        - Movement type defines addition or reduction.
        """
        # Verify product exists in tenant
        product = (
            self.db.query(Product)
            .filter(Product.id == product_id, Product.business_id == self.business_id)
            .first()
        )
        if not product:
            raise NotFoundError(f"Product {product_id} not found in current business")

        if quantity <= Decimal("0"):
            raise BadRequestError("Inventory movement quantity must be positive")

        type_str = movement_type.value if isinstance(movement_type, MovementType) else movement_type

        movement = InventoryMovement(
            business_id=self.business_id,
            product_id=product_id,
            movement_type=type_str,
            quantity=quantity,
            unit_cost=unit_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
            created_by=created_by or self.user_id,
        )
        return self.save(movement)

    def get_stock(self, product_id: str) -> Decimal:
        """Calculate authoritative physical stock by summing all movements."""
        movements = self._base_query().filter(InventoryMovement.product_id == product_id).all()
        return sum((m.signed_quantity for m in movements), start=Decimal("0.000"))

    def list_movements_for_product(
        self, product_id: str, limit: int = 100
    ) -> list[InventoryMovement]:
        """Fetch movement audit trail for a product."""
        return (
            self._base_query()
            .filter(InventoryMovement.product_id == product_id)
            .order_by(InventoryMovement.created_at.desc())
            .limit(limit)
            .all()
        )
