"""
Integration test fixtures with PostgreSQL and real services.

Integration tests verify service interactions with real database connections
and actual external dependencies, providing confidence in system behavior
without full HTTP stack overhead.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

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
)

# Force integration test environment
os.environ["TEST_TYPE"] = "integration"


# Function-scoped event loop for Integration Tests (PostgreSQL Compatibility)
@pytest.fixture(scope="function")
def event_loop():
    """Function-scoped event loop for Integration Tests with PostgreSQL."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# PostgreSQL database fixtures with function scope for integration tests
@pytest_asyncio.fixture(scope="function")
async def integration_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create PostgreSQL engine for each integration test."""
    from tests.fixtures.database import DatabaseStrategy, create_test_engine

    strategy = DatabaseStrategy.INTEGRATION
    engine = create_test_engine(strategy)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def integration_schema(integration_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """Create database schema for each integration test."""
    async with integration_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with integration_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(integration_engine: AsyncEngine, integration_schema) -> AsyncGenerator[AsyncSession, None]:
    """Create isolated database session for integration test."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

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
            await transaction.rollback()


# Real Repository Instances (no mocks!)
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


# Real Service Instances (with real dependencies!)
@pytest_asyncio.fixture
async def deepl_translator():
    """Real DeepL translator (if API key available, otherwise skip)."""
    if not settings.deepl_api_key:
        pytest.skip("DeepL API key not available for integration tests")

    executor = ThreadPoolExecutor(max_workers=2)
    translator = DeepLTranslator(api_key=settings.deepl_api_key, executor=executor)

    yield translator

    # Cleanup
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


# Factory fixtures for integration tests
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


# Test scenario fixtures
@pytest_asyncio.fixture
async def test_room_with_users(db_session, room_factory, user_factory):
    """Create a room with multiple users for integration testing."""
    # Create room
    room = await room_factory.create(db_session, name="Integration Test Room")

    # Create users in the room
    admin = await user_factory.create_admin(db_session, current_room_id=room.id)
    user1 = await user_factory.create(db_session,
                                     username="user1_integration",
                                     email="user1@integration.test",
                                     current_room_id=room.id,
                                     preferred_language="en")
    user2 = await user_factory.create(db_session,
                                     username="user2_integration",
                                     email="user2@integration.test",
                                     current_room_id=room.id,
                                     preferred_language="de")

    return {
        "room": room,
        "admin": admin,
        "users": [user1, user2],
        "english_user": user1,
        "german_user": user2,
    }


@pytest_asyncio.fixture
async def test_conversation_scenario(db_session, conversation_factory, user_factory, room_factory):
    """Create a conversation scenario for integration testing."""
    # Create room and users
    room = await room_factory.create(db_session, name="Conversation Test Room")

    user1 = await user_factory.create(db_session,
                                     username="conv_user1",
                                     email="conv1@test.com",
                                     current_room_id=room.id)
    user2 = await user_factory.create(db_session,
                                     username="conv_user2",
                                     email="conv2@test.com",
                                     current_room_id=room.id)
    user3 = await user_factory.create(db_session,
                                     username="conv_user3",
                                     email="conv3@test.com",
                                     current_room_id=room.id)

    # Create private conversation
    private_conv = await conversation_factory.create_private(
        db_session, room=room, participants=[user1, user2]
    )

    # Create group conversation
    group_conv = await conversation_factory.create_group(
        db_session, room=room, participants=[user1, user2, user3]
    )

    return {
        "room": room,
        "users": [user1, user2, user3],
        "private_conversation": private_conv,
        "group_conversation": group_conv,
    }