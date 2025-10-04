"""
Unit test fixtures with SQLite and mocked dependencies.

Modernized for pytest-asyncio 1.2.0 (October 2025):
- No event_loop fixture (removed in 1.x)
- Uses loop_scope="function" for all fixtures
- Clean separation: SQLite for speed, mocks for isolation

Unit tests should be:
- Fast (< 5s total)
- Isolated (no external dependencies)
- Deterministic (no flakiness)
"""

import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.interfaces.translator import TranslatorInterface
from app.models.ai_entity import AIEntity, AIEntityStatus
from app.models.user import User
from tests.fixtures import (
    ConversationFactory,
    MessageFactory,
    RoomFactory,
    UserFactory,
)

# Force unit test environment
os.environ["TEST_TYPE"] = "unit"


# ============================================================================
# AI-Specific Fixtures for Unit Tests
# ============================================================================


@pytest.fixture
def sample_ai_entity(sample_ai_entity_data):
    """Create sample AI entity for unit tests."""
    return AIEntity(
        id=1,
        **sample_ai_entity_data,
        status=AIEntityStatus.ONLINE,
        temperature=0.7,
        max_tokens=1024,
    )


@pytest.fixture
def sample_user(sample_user_data):
    """Create sample user for unit tests."""
    return User(
        id=2,
        username=sample_user_data["username"],
        email=sample_user_data["email"],
    )


@pytest.fixture
def mock_ai_provider():
    """Create mock AI provider for testing."""
    return AsyncMock()


@pytest.fixture
def mock_context_service():
    """Create mock AI context service for testing."""
    return AsyncMock()


@pytest.fixture
def mock_message_repo():
    """Create mock message repository for testing."""
    return AsyncMock()


@pytest.fixture
def mock_memory_repo():
    """Create mock AI memory repository for testing."""
    return AsyncMock()


# ============================================================================
# Database Fixtures (SQLite in-memory)
# ============================================================================


@pytest_asyncio.fixture(loop_scope="function")
async def unit_engine():
    """
    SQLite in-memory engine for unit tests.

    Function-scoped for maximum isolation.
    Uses StaticPool to maintain in-memory database during test.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Enable foreign key constraints for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(unit_engine):
    """
    Isolated database session for each unit test.

    Each test gets a fresh session. Factories handle their own commits.
    Session is closed after test completes.
    """
    async with AsyncSession(unit_engine, expire_on_commit=False) as session:
        yield session
        # Session cleanup happens automatically at context exit


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def mock_translator():
    """Mock translator implementing TranslatorInterface."""
    return AsyncMock(spec=TranslatorInterface)


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


@pytest.fixture
def message_factory():
    """Message factory for creating test messages."""
    return MessageFactory


@pytest.fixture
def conversation_factory():
    """Conversation factory for creating test conversations."""
    return ConversationFactory


# ============================================================================
# Quick Test Data Fixtures (for simple tests)
# ============================================================================


@pytest_asyncio.fixture
async def test_user(db_session, user_factory):
    """Quick access to a test user for simple unit tests."""
    return await user_factory.create(db_session)


@pytest_asyncio.fixture
async def test_admin(db_session, user_factory):
    """Quick access to an admin user for simple unit tests."""
    return await user_factory.create_admin(db_session)


@pytest_asyncio.fixture
async def test_room(db_session, room_factory):
    """Quick access to a test room for simple unit tests."""
    return await room_factory.create(db_session)


@pytest_asyncio.fixture
async def test_message(db_session, message_factory, test_user, test_room):
    """Quick access to a test message for simple unit tests."""
    return await message_factory.create_room_message(db_session, sender=test_user, room=test_room)
