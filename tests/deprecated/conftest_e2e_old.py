"""
E2E test fixtures with PostgreSQL and FastAPI HTTP client.

E2E tests verify the full application stack:
- Real PostgreSQL database
- Real FastAPI HTTP server (via AsyncClient)
- Full request/response cycle
- Authentication and authorization

Scope Strategy (Community Best Practice):
- event_loop: function-scoped (pytest-asyncio creates new loop per test)
- engine: function-scoped with NullPool (prevents asyncpg event loop binding)
- db_session: function-scoped with transaction rollback (test isolation)
- async_client: function-scoped (fresh HTTP client per test)

Why NullPool for E2E?
- Test isolation > performance
- No asyncpg connection pool binding issues
- Recommended by FastAPI and SQLAlchemy communities
"""

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.auth_utils import hash_password
from app.core.database import Base, get_db
from app.models.room import Room
from app.models.user import User
from main import app
from tests.fixtures import (
    DatabaseStrategy,
    create_test_engine,
)

# Force E2E test environment
os.environ["TEST_TYPE"] = "e2e"

# NOTE: .env.test is automatically loaded by pytest-env plugin (configured in pytest.ini)


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def e2e_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    PostgreSQL engine for E2E tests.

    Uses NullPool to prevent asyncpg event loop binding issues.
    Schema is created/dropped per test for complete isolation.
    """
    # Validate PostgreSQL is configured
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        pytest.skip(
            "E2E tests require DATABASE_URL environment variable.\n"
            "Set DATABASE_URL in .env.test or environment:\n"
            "  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/the_gathering_test"
        )

    if not DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://")):
        pytest.skip(
            f"E2E tests require PostgreSQL, got: {DATABASE_URL}\n"
            "Unit tests use SQLite, E2E tests need PostgreSQL for production parity."
        )

    strategy = DatabaseStrategy.E2E
    engine = create_test_engine(strategy)  # Uses NullPool for E2E

    # Create schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(e2e_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Isolated database session for each E2E test.

    Each test gets a fresh transaction that is rolled back after the test,
    ensuring no test data persists between tests.
    """
    session_maker = async_sessionmaker(
        e2e_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with session_maker() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            # Rollback if transaction is still active
            if transaction.is_active:
                await transaction.rollback()


# ============================================================================
# FastAPI HTTP Client Fixtures
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for E2E testing with dependency override.

    The client uses the test database session via dependency injection,
    ensuring all HTTP requests use the same isolated test database.
    """
    async def override_get_db():
        """Override get_db dependency to use test session."""
        yield db_session

    # Override database dependency
    app.dependency_overrides[get_db] = override_get_db

    # Create HTTP client
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as client:
        yield client

    # Clear overrides
    app.dependency_overrides.clear()


# ============================================================================
# Test Data Fixtures with Eager Loading
# ============================================================================

@pytest_asyncio.fixture
async def created_user(db_session, sample_user_data):
    """
    Create a user for E2E tests with SQLAlchemy 2.0 eager loading.

    Uses eager loading pattern to prevent lazy loading issues in async context.
    """
    user = User(
        email=sample_user_data["email"],
        username=sample_user_data["username"],
        password_hash=hash_password(sample_user_data["password"]),
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()

    # Reload with eager loading (SQLAlchemy 2.0 best practice)
    user = await db_session.scalar(select(User).where(User.id == user.id))
    db_session.expunge(user)
    return user


@pytest_asyncio.fixture
async def created_admin(db_session, sample_admin_data):
    """
    Create an admin for E2E tests with SQLAlchemy 2.0 eager loading.
    """
    admin = User(
        email=sample_admin_data["email"],
        username=sample_admin_data["username"],
        password_hash=hash_password(sample_admin_data["password"]),
        is_admin=True,
    )
    db_session.add(admin)
    await db_session.commit()

    # Reload with eager loading
    admin = await db_session.scalar(select(User).where(User.id == admin.id))
    db_session.expunge(admin)
    return admin


@pytest_asyncio.fixture
async def created_room(db_session, sample_room_data):
    """
    Create a room for E2E tests with SQLAlchemy 2.0 eager loading.
    """
    room = Room(
        name=sample_room_data["name"],
        description=sample_room_data["description"],
        max_users=sample_room_data["max_users"],
    )
    db_session.add(room)
    await db_session.commit()

    # Reload with eager loading
    room = await db_session.scalar(select(Room).where(Room.id == room.id))
    db_session.expunge(room)
    return room


# ============================================================================
# Authentication Helper Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def authenticated_user_headers(async_client, sample_user_data, created_user):
    """
    JWT token for authenticated user requests.

    Returns headers dict with Authorization: Bearer {token}
    """
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        },
    )
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def authenticated_admin_headers(async_client, sample_admin_data, created_admin):
    """
    JWT token for authenticated admin requests.

    Returns headers dict with Authorization: Bearer {token}
    """
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": sample_admin_data["email"],
            "password": sample_admin_data["password"],
        },
    )
    assert login_response.status_code == 200, f"Admin login failed: {login_response.text}"

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
