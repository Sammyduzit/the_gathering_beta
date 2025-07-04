import pytest
from unittest.mock import Mock
from datetime import datetime

from app.services.conversation_service import ConversationService
from app.services.room_service import RoomService
from app.models.user import User, UserStatus
from app.models.room import Room
from app.models.conversation import Conversation, ConversationType


@pytest.fixture
def mock_repositories():
    """Mock all repository dependencies."""
    return {
        "conversation_repo": Mock(),
        "message_repo": Mock(),
        "user_repo": Mock(),
        "room_repo": Mock(),
        "translation_service":Mock(),
    }


@pytest.fixture
def conversation_service(mock_repositories):
    """ConversationService with mocked dependencies."""
    return ConversationService(
        conversation_repo=mock_repositories["conversation_repo"],
        message_repo=mock_repositories["message_repo"],
        user_repo=mock_repositories["user_repo"],
        translation_service=mock_repositories["translation_service"],
    )


@pytest.fixture
def room_service(mock_repositories):
    """RoomService with mocked dependencies."""
    return RoomService(
        room_repo=mock_repositories["room_repo"],
        user_repo=mock_repositories["user_repo"],
        message_repo=mock_repositories["message_repo"],
        conversation_repo=mock_repositories["conversation_repo"],
        translation_service=mock_repositories["translation_service"],
    )


@pytest.fixture
def sample_user():
    """Sample User for unit tests."""
    return User(
        id=1,
        username="testuser",
        email="test@example.com",
        current_room_id=1,
        status=UserStatus.AVAILABLE,
        is_active=True,
        last_active=datetime.now(),
    )


@pytest.fixture
def sample_room():
    """Sample Room for unit tests."""
    return Room(
        id=1, name="Test Room", description="A test room", max_users=5, is_active=True
    )


@pytest.fixture
def sample_conversation():
    """Sample Conversation for unit tests."""
    return Conversation(
        id=1,
        room_id=1,
        conversation_type=ConversationType.PRIVATE,
        max_participants=2,
        is_active=True,
    )
