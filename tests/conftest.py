import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database, models
from app.database import Base
from app.main import app


@pytest.fixture(autouse=True)
def setup_test_db():
    """Use an in-memory SQLite database for each test."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    test_session_factory = sessionmaker(bind=test_engine)

    # Patch SessionLocal so the app uses the test DB
    database.SessionLocal = test_session_factory

    yield test_session_factory

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(setup_test_db):
    session = setup_test_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
