import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, Mock
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.services.conversation_service import ConversationService
from app.services.room_service import RoomService
from app.services.translation_service import TranslationService
from app.services.background_service import BackgroundService
from app.models.user import User, UserStatus
from app.models.room import Room
from app.models.conversation import Conversation, ConversationType
from app.models.message import Message


@pytest_asyncio.fixture
async def async_db_session():
    """Create async database session for testing."""
    # Use in-memory SQLite with aiosqlite driver for async testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_local() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def async_mock_repositories():
    """Mock all repository dependencies with AsyncMock."""
    return {
        "conversation_repo": AsyncMock(),
        "message_repo": AsyncMock(),
        "user_repo": AsyncMock(),
        "room_repo": AsyncMock(),
        "translation_repo": AsyncMock(),
    }


@pytest_asyncio.fixture
async def async_translation_service(async_mock_repositories):
    """Async TranslationService with mocked repositories."""
    return TranslationService(
        message_repo=async_mock_repositories["message_repo"],
        translation_repo=async_mock_repositories["translation_repo"],
    )


@pytest_asyncio.fixture
async def async_conversation_service(async_mock_repositories, async_translation_service):
    """Async ConversationService with mocked dependencies."""
    return ConversationService(
        conversation_repo=async_mock_repositories["conversation_repo"],
        message_repo=async_mock_repositories["message_repo"],
        user_repo=async_mock_repositories["user_repo"],
        translation_service=async_translation_service,
    )


@pytest_asyncio.fixture
async def async_room_service(async_mock_repositories, async_translation_service):
    """Async RoomService with mocked dependencies."""
    return RoomService(
        room_repo=async_mock_repositories["room_repo"],
        user_repo=async_mock_repositories["user_repo"],
        message_repo=async_mock_repositories["message_repo"],
        conversation_repo=async_mock_repositories["conversation_repo"],
        translation_service=async_translation_service,
    )


@pytest_asyncio.fixture
async def async_background_service(async_mock_repositories, async_translation_service):
    """Async BackgroundService with mocked dependencies."""
    return BackgroundService(
        translation_service=async_translation_service,
        message_translation_repo=async_mock_repositories["translation_repo"],
    )


@pytest.fixture
def sample_async_user():
    """Sample User for async tests."""
    return User(
        id=1,
        username="asyncuser",
        email="async@example.com",
        current_room_id=1,
        status=UserStatus.AVAILABLE,
        is_active=True,
        last_active=datetime.now(),
        preferred_language="en",
    )


@pytest.fixture
def sample_async_room():
    """Sample Room for async tests."""
    return Room(
        id=1,
        name="Async Test Room",
        description="An async test room",
        max_users=10,
        is_active=True,
        is_translation_enabled=True,
    )


@pytest.fixture
def sample_async_conversation():
    """Sample Conversation for async tests."""
    return Conversation(
        id=1,
        room_id=1,
        conversation_type=ConversationType.PRIVATE,
        max_participants=2,
        is_active=True,
    )


@pytest.fixture
def sample_async_message():
    """Sample Message for async tests."""
    return Message(
        id=1,
        content="Test async message",
        sender_id=1,
        room_id=1,
        conversation_id=None,
        sent_at=datetime.now(),
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_fastapi_background_tasks():
    """Mock FastAPI BackgroundTasks for testing."""
    return Mock()


@pytest_asyncio.fixture
async def async_test_data_setup(async_db_session):
    """Setup test data in async database session."""
    # Create test user
    test_user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        status=UserStatus.AVAILABLE,
        is_active=True,
        preferred_language="en",
    )
    async_db_session.add(test_user)

    # Create test room
    test_room = Room(
        name="Test Room",
        description="Test room description",
        max_users=5,
        is_active=True,
        is_translation_enabled=True,
    )
    async_db_session.add(test_room)

    await async_db_session.commit()
    await async_db_session.refresh(test_user)
    await async_db_session.refresh(test_room)

    return {
        "user": test_user,
        "room": test_room,
    }