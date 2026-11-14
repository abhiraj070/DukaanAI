"""Test verifying that database migrations execute cleanly from an empty database."""

import os
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_migrations_run_from_empty_db():
    """Verify that Alembic migrations run from scratch on an empty database to 'head'."""
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = backend_dir / "alembic.ini"
    assert alembic_ini_path.exists(), "alembic.ini not found"

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        sqlite_url = f"sqlite:///{db_path}"

        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)
        alembic_cfg.set_main_option("script_location", str(backend_dir / "migrations"))

        # Run migration from empty database to head
        command.upgrade(alembic_cfg, "head")

        # Inspect resulting database schema
        engine = create_engine(sqlite_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected_tables = {
            "businesses",
            "users",
            "business_memberships",
            "categories",
            "suppliers",
            "products",
            "supplier_products",
            "inventory_movements",
            "sales",
            "sale_items",
            "expenses",
            "customers",
            "credit_accounts",
            "credit_transactions",
            "credit_allocations",
            "audit_logs",
            "uploaded_documents",
            "document_extractions",
            "alembic_version",
        }

        missing = expected_tables - tables
        assert not missing, f"Migration failed to create tables: {missing}"

        engine.dispose()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except PermissionError:
                pass
