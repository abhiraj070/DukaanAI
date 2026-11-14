"""Tenant-scoped repository for Products and Catalogue."""

from decimal import Decimal

from app.models.catalogue import Product
from app.models.inventory import InventoryMovement
from app.repositories.base import BaseTenantRepository


class ProductRepository(BaseTenantRepository[Product]):
    """Tenant-scoped Product repository."""

    @property
    def model(self) -> type[Product]:
        return Product

    def get_by_sku(self, sku: str) -> Product | None:
        """Lookup product by SKU strictly within tenant."""
        return self._base_query().filter(Product.sku == sku).first()

    def create_product(
        self,
        name: str,
        selling_price: Decimal,
        cost_price: Decimal | None = None,
        sku: str | None = None,
        unit: str = "pc",
        category_id: str | None = None,
        supplier_id: str | None = None,
        min_stock_level: Decimal = Decimal("0.000"),
        reorder_quantity: Decimal = Decimal("0.000"),
    ) -> Product:
        """Create and persist a new product scoped to tenant."""
        product = Product(
            business_id=self.business_id,
            name=name,
            selling_price=selling_price,
            cost_price=cost_price,
            sku=sku,
            unit=unit,
            category_id=category_id,
            supplier_id=supplier_id,
            min_stock_level=min_stock_level,
            reorder_quantity=reorder_quantity,
        )
        return self.save(product)

    def get_reconciled_stock(self, product_id: str) -> Decimal:
        """Reconcile and calculate authoritative stock level from inventory movements."""
        movements = (
            self.db.query(InventoryMovement)
            .filter(
                InventoryMovement.business_id == self.business_id,
                InventoryMovement.product_id == product_id,
            )
            .all()
        )
        total_stock = Decimal("0.000")
        for m in movements:
            total_stock += m.signed_quantity
        return total_stock
