"""
E2E test fixtures with PostgreSQL and FastAPI HTTP client.

Modernized for pytest-asyncio 1.2.0 (October 2025):
- No event_loop fixture (removed in 1.x)
- Uses loop_scope="function" for all fixtures
- NullPool for PostgreSQL (prevents asyncpg event loop binding issues)

E2E tests verify the full application stack:
- Real PostgreSQL database
- Real FastAPI HTTP server (via AsyncClient)
- Full request/response cycle
- Authentication and authorization

Scope Strategy:
- All fixtures: function-scoped (maximum isolation)
- Engine: NullPool (no connection pooling, prevents asyncpg issues)
- Session: Transaction rollback (test isolation)
- AsyncClient: Fresh client per test
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.auth_utils import hash_password
from app.core.database import Base, get_db
from app.models.room import Room
from app.models.user import User
from main import app
from tests.fixtures import RoomFactory, UserFactory

# Force E2E test environment
os.environ["TEST_TYPE"] = "e2e"


# ============================================================================
# Database Fixtures (PostgreSQL with NullPool)
# ============================================================================


@pytest_asyncio.fixture(loop_scope="function")
async def e2e_engine():
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

    # Convert postgresql:// to postgresql+asyncpg:// if needed
    if DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+asyncpg://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        DATABASE_URL,
        poolclass=NullPool,  # Essential for pytest + asyncpg
        echo=False,
    )

    # Create schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(e2e_engine):
    """
    Isolated database session for each E2E test.

    Each test gets a fresh session. Factories handle their own commits.
    Session is closed after test completes.
    """
    async with AsyncSession(e2e_engine, expire_on_commit=False) as session:
        yield session
        # Session cleanup happens automatically at context exit


# ============================================================================
# FastAPI HTTP Client Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def async_client(db_session):
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client

    # Clear overrides
    app.dependency_overrides.clear()


# ============================================================================
# Test Data Fixtures with Eager Loading (SQLAlchemy 2.0 Best Practice)
# ============================================================================


@pytest_asyncio.fixture
async def created_user(db_session):
    """
    Create a user for E2E tests with SQLAlchemy 2.0 eager loading.

    Uses eager loading pattern to prevent lazy loading issues in async context.
    """
    user = User(
        email="user@example.com",
        username="testuser",
        password_hash=hash_password("password123"),
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()

    # Reload with eager loading (SQLAlchemy 2.0 best practice)
    user = await db_session.scalar(select(User).where(User.id == user.id))
    db_session.expunge(user)
    return user


@pytest_asyncio.fixture
async def created_admin(db_session):
    """
    Create an admin for E2E tests with SQLAlchemy 2.0 eager loading.
    """
    admin = User(
        email="admin@example.com",
        username="testadmin",
        password_hash=hash_password("adminpass123"),
        is_admin=True,
    )
    db_session.add(admin)
    await db_session.commit()

    # Reload with eager loading
    admin = await db_session.scalar(select(User).where(User.id == admin.id))
    db_session.expunge(admin)
    return admin


@pytest_asyncio.fixture
async def created_room(db_session):
    """
    Create a room for E2E tests with SQLAlchemy 2.0 eager loading.
    """
    room = Room(
        name="Test Room",
        description="A test room for testing purposes",
        max_users=10,
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
async def authenticated_user_headers(async_client, created_user):
    """
    JWT token for authenticated user requests.

    Returns headers dict with Authorization: Bearer {token}
    """
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "user@example.com",
            "password": "password123",
        },
    )
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def authenticated_admin_headers(async_client, created_admin):
    """
    JWT token for authenticated admin requests.

    Returns headers dict with Authorization: Bearer {token}
    """
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "password": "adminpass123",
        },
    )
    assert login_response.status_code == 200, f"Admin login failed: {login_response.text}"

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Factory Fixtures
# ============================================================================


@pytest.fixture
def user_factory():
    """User factory for creating test users."""
    return UserFactory


@pytest.fixture
def room_factory():
    """Room factory for creating test rooms."""
    return RoomFactory


# ============================================================================
# AI Entity Fixtures for ARQ Worker Tests
# ============================================================================


@pytest_asyncio.fixture
async def created_ai_entity(db_session):
    """Create AI entity for ARQ worker tests."""
    from app.models.ai_entity import AIEntity, AIEntityStatus

    ai_entity = AIEntity(
        name="test_ai",
        display_name="Test AI",
        system_prompt="You are a test AI assistant",
        model_name="gpt-4o-mini",
        status=AIEntityStatus.ONLINE,
        temperature=0.7,
        max_tokens=1024,
    )
    db_session.add(ai_entity)
    await db_session.commit()

    ai_entity = await db_session.scalar(
        select(AIEntity).where(AIEntity.id == ai_entity.id)
    )
    db_session.expunge(ai_entity)
    return ai_entity


@pytest_asyncio.fixture
async def created_conversation(db_session, created_room, created_user):
    """Create conversation for ARQ worker tests."""
    from app.models.conversation import Conversation, ConversationType

    conversation = Conversation(
        room_id=created_room.id,
        conversation_type=ConversationType.PRIVATE,
        max_participants=2,
    )
    db_session.add(conversation)
    await db_session.commit()

    conversation = await db_session.scalar(
        select(Conversation).where(Conversation.id == conversation.id)
    )
    db_session.expunge(conversation)
    return conversation


@pytest_asyncio.fixture
async def async_db_session(db_session):
    """Alias for db_session for ARQ worker tests."""
    return db_session
