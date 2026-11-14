"""Test fixtures for DukaanAI backend."""

from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - Ensure all models are registered on Base.metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from tests.fixtures.demo_data import create_demo_tenants


# SQLite in-memory test database with foreign keys enabled
@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Provide a completely isolated in-memory database session for each test."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all schema tables
    Base.metadata.create_all(bind=test_engine)

    TestSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False
    )
    session = TestSessionLocal()

    # Override get_db dependency in FastAPI app
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        app.dependency_overrides.clear()


@pytest.fixture
def tenants(db_session: Session) -> dict[str, dict]:
    """Provide pre-populated isolated demo tenants A & B."""
    return create_demo_tenants(db_session)


@pytest.fixture
def client(db_session: Session):
    """Create a synchronous TestClient for the FastAPI app."""
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
async def async_client(db_session: Session):
    """Create an asynchronous HTTP test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
