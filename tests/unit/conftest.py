"""
Unit test fixtures with SQLite and mocked dependencies.

Unit tests should be fast, isolated, and deterministic. This module provides:
- SQLite in-memory database for speed
- Comprehensive mocks for all external dependencies
- Factory-based test data creation
- Automatic cleanup between tests
"""

import asyncio
import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from app.core.database import Base
from app.interfaces.translator import TranslatorInterface
from app.services.background_service import BackgroundService
from app.services.conversation_service import ConversationService
from app.services.room_service import RoomService
from app.services.translation_service import TranslationService
from tests.fixtures import (
    DatabaseStrategy,
    create_test_engine,
    create_test_session,
    UserFactory,
    RoomFactory,
    MessageFactory,
    ConversationFactory,
    MockRepositories,
    MockServices,
    create_mock_dependencies
)

# Force unit test environment
os.environ["TEST_TYPE"] = "unit"


# Session-scoped event loop for Unit Tests (SQLite Performance)
@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for Unit Tests with SQLite."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def unit_engine():
    """SQLite engine for unit tests - fast and isolated."""
    strategy = DatabaseStrategy.UNIT
    engine = create_test_engine(strategy)

    # Create schema once per session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(unit_engine):
    """Isolated database session for each unit test with automatic rollback."""
    session_maker = create_test_session(unit_engine)

    async with session_maker() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            # Check if transaction is still active before rollback
            if transaction.is_active:
                await transaction.rollback()


@pytest_asyncio.fixture
async def mock_repositories():
    """Mocked repositories for unit testing - no real database operations."""
    return MockRepositories()


@pytest_asyncio.fixture
async def mock_services():
    """Mocked services for unit testing - no external dependencies."""
    return MockServices()


@pytest_asyncio.fixture
async def mock_dependencies():
    """Complete set of mocked dependencies for complex unit tests."""
    return create_mock_dependencies()


# Factory fixtures for unit tests
@pytest_asyncio.fixture
async def user_factory():
    """User factory for creating test users."""
    return UserFactory


@pytest_asyncio.fixture
async def room_factory():
    """Room factory for creating test rooms."""
    return RoomFactory


@pytest_asyncio.fixture
async def message_factory():
    """Message factory for creating test messages."""
    return MessageFactory


@pytest_asyncio.fixture
async def conversation_factory():
    """Conversation factory for creating test conversations."""
    return ConversationFactory


# Service fixtures with clean dependency injection
@pytest_asyncio.fixture
async def mock_translator():
    """Mock translator implementing TranslatorInterface."""
    return AsyncMock(spec=TranslatorInterface)


@pytest_asyncio.fixture
async def translation_service(mock_translator, mock_repositories):
    """Real TranslationService with mocked dependencies."""
    return TranslationService(
        translator=mock_translator,
        message_repo=mock_repositories.message_repo,
        translation_repo=mock_repositories.translation_repo,
    )


@pytest_asyncio.fixture
async def room_service(mock_repositories, translation_service):
    """Real RoomService with mocked dependencies."""
    return RoomService(
        room_repo=mock_repositories.room_repo,
        user_repo=mock_repositories.user_repo,
        message_repo=mock_repositories.message_repo,
        conversation_repo=mock_repositories.conversation_repo,
        message_translation_repo=mock_repositories.translation_repo,
        translation_service=translation_service,
    )


@pytest_asyncio.fixture
async def conversation_service(mock_repositories, translation_service):
    """Real ConversationService with mocked dependencies."""
    return ConversationService(
        conversation_repo=mock_repositories.conversation_repo,
        message_repo=mock_repositories.message_repo,
        user_repo=mock_repositories.user_repo,
        room_repo=mock_repositories.room_repo,
        translation_service=translation_service,
    )


@pytest_asyncio.fixture
async def background_service(translation_service, mock_repositories):
    """Real BackgroundService with mocked dependencies."""
    return BackgroundService(
        translation_service=translation_service,
        message_translation_repo=mock_repositories.translation_repo,
    )


# Quick test data fixtures
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
    return await message_factory.create_room_message(
        db_session, sender=test_user, room=test_room
    )