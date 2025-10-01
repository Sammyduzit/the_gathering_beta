"""
Integration test fixtures with PostgreSQL and real services.

Integration tests verify:
- Real database operations with PostgreSQL
- Real service interactions
- Database constraints and transactions
- NO HTTP layer (use e2e tests for that)

Architecture (Learned from asyncpg + pytest-asyncio issues):
- event_loop: function-scoped (pytest-asyncio creates new loop per test anyway)
- engine: function-scoped with NullPool (prevents asyncpg event loop binding errors)
- db_session: function-scoped with transaction rollback (test isolation)

Why NullPool?
- asyncpg connection pools bind to a specific event loop
- pytest-asyncio creates a new loop per test (even with session-scoped fixtures)
- NullPool = no pooling = fresh connection per test = no event loop conflicts
- Performance is acceptable for integration tests (< 30s total)
"""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.implementations.deepl_translator import DeepLTranslator
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.message_translation_repository import MessageTranslationRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from app.services.background_service import BackgroundService
from app.services.conversation_service import ConversationService
from app.services.room_service import RoomService
from app.services.translation_service import TranslationService
from tests.fixtures import (
    UserFactory,
    RoomFactory,
    MessageFactory,
    ConversationFactory,
    DatabaseStrategy,
    create_test_engine,
)

# Force integration test environment
os.environ["TEST_TYPE"] = "integration"


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def integration_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    PostgreSQL engine for each integration test.

    Uses NullPool to prevent asyncpg event loop binding issues.
    Schema is created/dropped per test for complete isolation.
    """
    strategy = DatabaseStrategy.INTEGRATION
    engine = create_test_engine(strategy)  # Uses NullPool from database.py

    # Create schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(integration_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Isolated database session with automatic transaction rollback.

    Each test gets a fresh transaction that is rolled back after the test,
    ensuring no test data persists between tests.
    """
    session_maker = async_sessionmaker(
        integration_engine,
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
# Repository Fixtures (Real Implementations)
# ============================================================================

@pytest_asyncio.fixture
async def user_repo(db_session):
    """Real UserRepository with PostgreSQL."""
    return UserRepository(db_session)


@pytest_asyncio.fixture
async def room_repo(db_session):
    """Real RoomRepository with PostgreSQL."""
    return RoomRepository(db_session)


@pytest_asyncio.fixture
async def message_repo(db_session):
    """Real MessageRepository with PostgreSQL."""
    return MessageRepository(db_session)


@pytest_asyncio.fixture
async def conversation_repo(db_session):
    """Real ConversationRepository with PostgreSQL."""
    return ConversationRepository(db_session)


@pytest_asyncio.fixture
async def message_translation_repo(db_session):
    """Real MessageTranslationRepository with PostgreSQL."""
    return MessageTranslationRepository(db_session)


# ============================================================================
# Service Fixtures (Real Implementations)
# ============================================================================

@pytest_asyncio.fixture
async def deepl_translator():
    """
    Real DeepL translator (skip tests if no API key available).

    Integration tests that require translation will be skipped
    if DEEPL_API_KEY environment variable is not set.
    """
    if not settings.deepl_api_key:
        pytest.skip("DeepL API key not available for integration tests")

    executor = ThreadPoolExecutor(max_workers=2)
    translator = DeepLTranslator(api_key=settings.deepl_api_key, executor=executor)

    yield translator

    await translator.dispose()


@pytest_asyncio.fixture
async def translation_service(deepl_translator, message_repo, message_translation_repo):
    """Real TranslationService with real DeepL API."""
    return TranslationService(
        translator=deepl_translator,
        message_repo=message_repo,
        translation_repo=message_translation_repo,
    )


@pytest_asyncio.fixture
async def room_service(room_repo, user_repo, message_repo, conversation_repo, message_translation_repo, translation_service):
    """Real RoomService with all real dependencies."""
    return RoomService(
        room_repo=room_repo,
        user_repo=user_repo,
        message_repo=message_repo,
        conversation_repo=conversation_repo,
        message_translation_repo=message_translation_repo,
        translation_service=translation_service,
    )


@pytest_asyncio.fixture
async def conversation_service(conversation_repo, message_repo, user_repo, room_repo, translation_service):
    """Real ConversationService with all real dependencies."""
    return ConversationService(
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        user_repo=user_repo,
        room_repo=room_repo,
        translation_service=translation_service,
    )


@pytest_asyncio.fixture
async def background_service(translation_service, message_translation_repo):
    """Real BackgroundService with real dependencies."""
    return BackgroundService(
        translation_service=translation_service,
        message_translation_repo=message_translation_repo,
    )


# ============================================================================
# Factory Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def user_factory():
    """User factory for creating test users in PostgreSQL."""
    return UserFactory


@pytest_asyncio.fixture
async def room_factory():
    """Room factory for creating test rooms in PostgreSQL."""
    return RoomFactory


@pytest_asyncio.fixture
async def message_factory():
    """Message factory for creating test messages in PostgreSQL."""
    return MessageFactory


@pytest_asyncio.fixture
async def conversation_factory():
    """Conversation factory for creating test conversations in PostgreSQL."""
    return ConversationFactory
