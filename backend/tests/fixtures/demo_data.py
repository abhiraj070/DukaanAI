"""Isolated deterministic test fixtures for multi-tenant tests."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.context import BusinessContext
from app.core.security import hash_password
from app.models.catalogue import Category, Product, Supplier
from app.models.identity import Business, BusinessMembership, User
from app.models.inventory import InventoryMovement, MovementType
from app.models.udhar import CreditAccount, Customer


def create_demo_tenants(db: Session) -> dict[str, dict]:
    """Create two fully isolated tenant businesses (Tenant A and Tenant B)."""
    # Tenant A
    user_a = User(
        email="sharma@sharmakirana.test",
        hashed_password=hash_password("Kirana@12345"),
        full_name="Rajesh Sharma",
    )
    db.add(user_a)
    db.flush()

    business_a = Business(
        name="Sharma Kirana Store",
        slug="sharma-kirana",
        region="Delhi-NCR",
        currency="INR",
        timezone="Asia/Kolkata",
    )
    db.add(business_a)
    db.flush()

    membership_a = BusinessMembership(
        user_id=user_a.id,
        business_id=business_a.id,
        role="owner",
    )
    db.add(membership_a)

    cat_a = Category(business_id=business_a.id, name="Atta & Grains")
    sup_a = Supplier(business_id=business_a.id, name="Delhi Wholesale Grains", lead_time_days=2)
    db.add_all([cat_a, sup_a])
    db.flush()

    prod_a = Product(
        business_id=business_a.id,
        category_id=cat_a.id,
        supplier_id=sup_a.id,
        name="Aashirvaad Shudh Chakki Atta 10kg",
        sku="ATTA-AASH-10KG",
        unit="packet",
        selling_price=Decimal("450.00"),
        cost_price=Decimal("380.00"),
        min_stock_level=Decimal("5.000"),
        reorder_quantity=Decimal("20.000"),
    )
    db.add(prod_a)
    db.flush()

    # Initial stock movement for Tenant A (+25 packets)
    inv_a = InventoryMovement(
        business_id=business_a.id,
        product_id=prod_a.id,
        movement_type=MovementType.PURCHASE_RECEIPT.value,
        quantity=Decimal("25.000"),
        unit_cost=Decimal("380.00"),
        reference_type="PURCHASE_ORDER",
        reference_id="PO-001",
    )
    db.add(inv_a)

    cust_a = Customer(
        business_id=business_a.id,
        display_name="Mukesh Gupta",
        phone_e164="+919810012345",
    )
    db.add(cust_a)
    db.flush()

    credit_acc_a = CreditAccount(
        business_id=business_a.id,
        customer_id=cust_a.id,
        credit_limit=Decimal("5000.00"),
        currency="INR",
    )
    db.add(credit_acc_a)
    db.flush()

    # -------------------------------------------------------------
    # Tenant B
    user_b = User(
        email="verma@vermasuper.test",
        hashed_password=hash_password("Super@12345"),
        full_name="Sunil Verma",
    )
    db.add(user_b)
    db.flush()

    business_b = Business(
        name="Verma Supermarket",
        slug="verma-supermarket",
        region="Mumbai",
        currency="INR",
        timezone="Asia/Kolkata",
    )
    db.add(business_b)
    db.flush()

    membership_b = BusinessMembership(
        user_id=user_b.id,
        business_id=business_b.id,
        role="owner",
    )
    db.add(membership_b)

    cat_b = Category(business_id=business_b.id, name="Dairy & Milk")
    sup_b = Supplier(business_id=business_b.id, name="Maharashtra Dairy Co", lead_time_days=1)
    db.add_all([cat_b, sup_b])
    db.flush()

    prod_b = Product(
        business_id=business_b.id,
        category_id=cat_b.id,
        supplier_id=sup_b.id,
        name="Amul Butter 500g",
        sku="DAIRY-AMUL-500G",
        unit="pc",
        selling_price=Decimal("275.00"),
        cost_price=Decimal("240.00"),
        min_stock_level=Decimal("10.000"),
        reorder_quantity=Decimal("30.000"),
    )
    db.add(prod_b)
    db.flush()

    inv_b = InventoryMovement(
        business_id=business_b.id,
        product_id=prod_b.id,
        movement_type=MovementType.PURCHASE_RECEIPT.value,
        quantity=Decimal("50.000"),
        unit_cost=Decimal("240.00"),
        reference_type="PURCHASE_ORDER",
        reference_id="PO-B01",
    )
    db.add(inv_b)

    cust_b = Customer(
        business_id=business_b.id,
        display_name="Anita Deshmukh",
        phone_e164="+919820067890",
    )
    db.add(cust_b)
    db.flush()

    credit_acc_b = CreditAccount(
        business_id=business_b.id,
        customer_id=cust_b.id,
        credit_limit=Decimal("10000.00"),
        currency="INR",
    )
    db.add(credit_acc_b)
    db.commit()

    return {
        "tenant_a": {
            "business": business_a,
            "user": user_a,
            "product": prod_a,
            "customer": cust_a,
            "credit_account": credit_acc_a,
            "context": BusinessContext(
                business_id=business_a.id,
                user_id=user_a.id,
                role="owner",
                business_name=business_a.name,
                currency=business_a.currency,
                timezone=business_a.timezone,
            ),
        },
        "tenant_b": {
            "business": business_b,
            "user": user_b,
            "product": prod_b,
            "customer": cust_b,
            "credit_account": credit_acc_b,
            "context": BusinessContext(
                business_id=business_b.id,
                user_id=user_b.id,
                role="owner",
                business_name=business_b.name,
                currency=business_b.currency,
                timezone=business_b.timezone,
            ),
        },
    }
