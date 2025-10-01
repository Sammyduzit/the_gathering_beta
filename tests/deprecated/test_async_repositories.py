import pytest

from app.models.message import Message
from app.models.room import Room
from app.models.user import User, UserStatus
from app.repositories.message_repository import MessageRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository


@pytest.mark.unit
class TestAsyncUserRepository:
    """Unit tests for UserRepository with SQLite and factories."""

    async def test_create_user_success(self, db_session, user_factory):
        """Test successful user creation using factory."""
        # Arrange
        user_repo = UserRepository(db_session)
        user_data = user_factory.build(
            username="testuser",
            email="test@example.com"
        )

        # Act
        created_user = await user_repo.create(user_data)

        # Assert
        assert created_user.id is not None
        assert created_user.username == "testuser"
        assert created_user.email == "test@example.com"
        assert created_user.is_active is True

    async def test_get_by_id_success(self, db_session, test_user):
        """Test successful user retrieval by ID."""
        # Arrange
        user_repo = UserRepository(db_session)

        # Act
        retrieved_user = await user_repo.get_by_id(test_user.id)

        # Assert
        assert retrieved_user is not None
        assert retrieved_user.id == test_user.id
        assert retrieved_user.username == test_user.username

    async def test_get_by_id_not_found(self, db_session):
        """Test user retrieval when ID not found."""
        # Arrange
        user_repo = UserRepository(db_session)

        # Act
        retrieved_user = await user_repo.get_by_id(999)

        # Assert
        assert retrieved_user is None

    async def test_get_by_username_success(self, db_session, test_user):
        """Test successful user retrieval by username."""
        # Arrange
        user_repo = UserRepository(db_session)

        # Act
        retrieved_user = await user_repo.get_by_username(test_user.username)

        # Assert
        assert retrieved_user is not None
        assert retrieved_user.username == test_user.username

    async def test_get_by_email_success(self, db_session, test_user):
        """Test successful user retrieval by email."""
        # Arrange
        user_repo = UserRepository(db_session)

        # Act
        retrieved_user = await user_repo.get_by_email(test_user.email)

        # Assert
        assert retrieved_user is not None
        assert retrieved_user.email == test_user.email

    async def test_update_user_success(self, db_session, test_user):
        """Test successful user update."""
        # Arrange
        user_repo = UserRepository(db_session)
        test_user.preferred_language = "de"

        # Act
        updated_user = await user_repo.update(test_user)

        # Assert
        assert updated_user.preferred_language == "de"

    async def test_username_exists_true(self, db_session, test_user):
        """Test username existence check when username exists."""
        # Arrange
        user_repo = UserRepository(db_session)

        # Act
        exists = await user_repo.username_exists(test_user.username)

        # Assert
        assert exists is True

    async def test_username_exists_false(self, db_session):
        """Test username existence check when username doesn't exist."""
        # Arrange
        user_repo = UserRepository(db_session)

        # Act
        exists = await user_repo.username_exists("nonexistent")

        # Assert
        assert exists is False


@pytest.mark.unit
class TestAsyncRoomRepository:
    """Unit tests for RoomRepository with SQLite and factories."""

    async def test_create_room_success(self, db_session, room_factory):
        """Test successful room creation using factory."""
        # Arrange
        room_repo = RoomRepository(db_session)
        room_data = room_factory.build(
            name="Test Room",
            description="Test room description",
            max_users=5
        )

        # Act
        created_room = await room_repo.create(room_data)

        # Assert
        assert created_room.id is not None
        assert created_room.name == "Test Room"
        assert created_room.is_active is True
        assert created_room.is_translation_enabled is True

    async def test_get_active_rooms(self, db_session, test_room):
        """Test retrieval of active rooms."""
        # Arrange
        room_repo = RoomRepository(db_session)

        # Act
        active_rooms = await room_repo.get_active_rooms()

        # Assert
        assert len(active_rooms) >= 1
        assert all(room.is_active for room in active_rooms)

    async def test_get_user_count(self, db_session, test_user, test_room):
        """Test user count in room retrieval."""
        # Arrange
        room_repo = RoomRepository(db_session)

        # Act
        count = await room_repo.get_user_count(test_room.id)

        # Assert
        assert count >= 0  # Can be 0 if no users in room

    async def test_update_room_success(self, db_session, test_user, test_room):
        """Test successful room update."""
        # Arrange
        room_repo = RoomRepository(db_session)
        test_room.description = "Updated description"

        # Act
        updated_room = await room_repo.update(test_room)

        # Assert
        assert updated_room.description == "Updated description"


@pytest.mark.unit
class TestAsyncMessageRepository:
    """Async unit tests for MessageRepository."""

    async def test_create_message_success(self, db_session, test_user, test_room):
        """Test successful message creation."""
        # Arrange
        message_repo = MessageRepository(db_session)

        message_data = Message(
            content="Test message content",
            sender_id=test_user.id,
            room_id=test_room.id,
            conversation_id=None,
        )

        # Act
        created_message = await message_repo.create(message_data)

        # Assert
        assert created_message.id is not None
        assert created_message.content == "Test message content"
        assert created_message.sender_id == test_user.id
        assert created_message.room_id == test_room.id

    async def test_get_room_messages_success(self, db_session, test_user, test_room):
        """Test successful retrieval of room messages."""
        # Arrange
        message_repo = MessageRepository(db_session)

        # Create a test message first
        message_data = Message(
            content="Test room message",
            sender_id=test_user.id,
            room_id=test_room.id,
            conversation_id=None,
        )
        await message_repo.create(message_data)

        # Act
        messages, count = await message_repo.get_room_messages(room_id=test_room.id, page=1, page_size=10)

        # Assert
        assert count >= 1
        assert len(messages) >= 1
        assert messages[0].room_id == test_room.id

    async def test_get_conversation_messages_empty(self, db_session):
        """Test retrieval of conversation messages when none exist."""
        # Arrange
        message_repo = MessageRepository(db_session)
        conversation_id = 999  # Non-existent conversation

        # Act
        messages, count = await message_repo.get_conversation_messages(
            conversation_id=conversation_id, page=1, page_size=10
        )

        # Assert
        assert count == 0
        assert len(messages) == 0

    async def test_get_all_messages_pagination(self, db_session):
        """Test message pagination."""
        # Arrange
        message_repo = MessageRepository(db_session)

        # Act
        messages = await message_repo.get_all(limit=5, offset=0)

        # Assert
        assert len(messages) <= 5
        assert isinstance(messages, list)

    async def test_exists_message(self, db_session, test_user, test_room):
        """Test message existence check."""
        # Arrange
        message_repo = MessageRepository(db_session)

        # Create a test message
        message_data = Message(
            content="Test existence check",
            sender_id=test_user.id,
            room_id=test_room.id,
        )
        created_message = await message_repo.create(message_data)

        # Act
        exists = await message_repo.exists(created_message.id)

        # Assert
        assert exists is True

    async def test_delete_message_success(self, db_session, test_user, test_room):
        """Test successful message deletion."""
        # Arrange
        message_repo = MessageRepository(db_session)

        # Create a test message
        message_data = Message(
            content="Test deletion",
            sender_id=test_user.id,
            room_id=test_room.id,
        )
        created_message = await message_repo.create(message_data)

        # Act
        deleted = await message_repo.delete(created_message.id)

        # Assert
        assert deleted is True

        # Verify message no longer exists
        exists = await message_repo.exists(created_message.id)
        assert exists is False
