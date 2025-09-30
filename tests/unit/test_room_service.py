"""
Clean unit tests for RoomService using dependency injection.

Tests demonstrate proper service testing with mocked dependencies,
factory pattern for test data, and comprehensive business logic coverage.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.room import Room
from app.models.user import User, UserStatus


@pytest.mark.unit
class TestRoomService:
    """Unit tests for RoomService with clean dependency injection."""

    async def test_get_all_rooms_success(self, room_service, mock_repositories):
        """Test successful retrieval of all active rooms."""
        # Arrange
        expected_rooms = [
            Room(id=1, name="Room 1", is_active=True),
            Room(id=2, name="Room 2", is_active=True),
        ]
        mock_repositories.room_repo.get_active_rooms.return_value = expected_rooms

        # Act
        result = await room_service.get_all_rooms()

        # Assert
        assert result == expected_rooms
        mock_repositories.room_repo.get_active_rooms.assert_called_once()

    async def test_create_room_success(self, room_service, mock_repositories):
        """Test successful room creation."""
        # Arrange
        name = "Test Room"
        description = "Test Description"
        max_users = 10
        is_translation_enabled = True

        # Mock name doesn't exist
        mock_repositories.room_repo.name_exists.return_value = False

        # Mock successful creation
        expected_room = Room(
            id=1,
            name=name,
            description=description,
            max_users=max_users,
            is_translation_enabled=is_translation_enabled
        )
        mock_repositories.room_repo.create.return_value = expected_room

        # Act
        result = await room_service.create_room(
            name=name,
            description=description,
            max_users=max_users,
            is_translation_enabled=is_translation_enabled,
        )

        # Assert
        assert result == expected_room
        mock_repositories.room_repo.name_exists.assert_called_once_with(name)
        mock_repositories.room_repo.create.assert_called_once()

    async def test_create_room_name_exists(self, room_service, mock_repositories):
        """Test room creation when name already exists."""
        # Arrange
        name = "Existing Room"
        mock_repositories.room_repo.name_exists.return_value = True

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await room_service.create_room(
                name=name,
                description="Test",
                max_users=10,
            )

        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value.detail)

    async def test_join_room_success(self, room_service, mock_repositories):
        """Test successful room joining."""
        # Arrange
        user = User(id=1, username="testuser", current_room_id=None)
        room_id = 5
        room = Room(id=room_id, name="Test Room", max_users=10)

        # Mock room exists
        mock_repositories.room_repo.get_by_id.return_value = room
        # Mock room not full
        mock_repositories.room_repo.get_user_count.side_effect = [5, 6]  # before and after
        # Mock user update
        mock_repositories.user_repo.update.return_value = AsyncMock()

        # Act
        result = await room_service.join_room(user, room_id)

        # Assert
        assert result["message"] == "Successfully joined room 'Test Room'"
        assert result["room_id"] == room_id
        assert result["user_count"] == 6
        assert user.current_room_id == room_id
        assert user.status == UserStatus.AVAILABLE

    async def test_join_room_full(self, room_service, mock_repositories):
        """Test joining room when it's full."""
        # Arrange
        user = User(id=1, username="testuser")
        room_id = 5
        room = Room(id=room_id, name="Full Room", max_users=2)

        # Mock room exists
        mock_repositories.room_repo.get_by_id.return_value = room
        # Mock room is full
        mock_repositories.room_repo.get_user_count.return_value = 2

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await room_service.join_room(user, room_id)

        assert exc_info.value.status_code == 409
        assert "is full" in str(exc_info.value.detail)

    async def test_leave_room_success(self, room_service, mock_repositories):
        """Test successful room leaving."""
        # Arrange
        room_id = 5
        user = User(id=1, username="testuser", current_room_id=room_id)
        room = Room(id=room_id, name="Test Room")

        # Mock room exists
        mock_repositories.room_repo.get_by_id.return_value = room
        # Mock user update
        mock_repositories.user_repo.update.return_value = AsyncMock()

        # Act
        result = await room_service.leave_room(user, room_id)

        # Assert
        assert result["message"] == "Left room 'Test Room'"
        assert result["room_id"] == room_id
        assert user.current_room_id is None
        assert user.status == UserStatus.AWAY

    async def test_leave_room_not_in_room(self, room_service, mock_repositories):
        """Test leaving room when user is not in that room."""
        # Arrange
        room_id = 5
        user = User(id=1, username="testuser", current_room_id=999)  # Different room
        room = Room(id=room_id, name="Test Room")

        # Mock room exists
        mock_repositories.room_repo.get_by_id.return_value = room

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await room_service.leave_room(user, room_id)

        assert exc_info.value.status_code == 400
        assert "not in room" in str(exc_info.value.detail)

    async def test_send_room_message_success_with_translation(self, mock_repositories):
        """Test sending room message with translation enabled."""
        # Arrange
        from app.services.room_service import RoomService

        room_id = 5
        user = User(id=1, username="sender", current_room_id=room_id, preferred_language="en")
        content = "Hello world"

        room = Room(id=room_id, name="Test Room", is_translation_enabled=True)
        message = AsyncMock()
        message.id = 5  # Not divisible by MESSAGE_CLEANUP_FREQUENCY

        # Mock translation service
        mock_translation_service = AsyncMock()
        mock_translation_service.translate_and_store_message.return_value = 2

        # Create service with mocked translation service
        room_service = RoomService(
            room_repo=mock_repositories.room_repo,
            user_repo=mock_repositories.user_repo,
            message_repo=mock_repositories.message_repo,
            conversation_repo=mock_repositories.conversation_repo,
            message_translation_repo=mock_repositories.translation_repo,
            translation_service=mock_translation_service,
        )

        # Mock room exists and user is in room
        mock_repositories.room_repo.get_by_id.return_value = room
        # Mock message creation
        mock_repositories.message_repo.create_room_message.return_value = message
        # Mock room users for translation
        room_users = [
            User(id=2, preferred_language="de", username="user2"),
            User(id=3, preferred_language="fr", username="user3"),
        ]
        mock_repositories.room_repo.get_users_in_room.return_value = room_users

        # Act
        result = await room_service.send_room_message(user, room_id, content)

        # Assert
        assert result == message
        mock_repositories.message_repo.create_room_message.assert_called_once()
        mock_translation_service.translate_and_store_message.assert_called_once()

    async def test_send_room_message_user_not_in_room(self, room_service, mock_repositories):
        """Test sending message when user is not in the room."""
        # Arrange
        room_id = 5
        user = User(id=1, username="sender", current_room_id=999)  # Different room
        room = Room(id=room_id, name="Test Room")

        # Mock room exists
        mock_repositories.room_repo.get_by_id.return_value = room

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await room_service.send_room_message(user, room_id, "Hello")

        assert exc_info.value.status_code == 403
        assert "must be in room" in str(exc_info.value.detail)

    async def test_get_room_messages_success(self, room_service, mock_repositories):
        """Test successful retrieval of room messages."""
        # Arrange
        room_id = 5
        user = User(id=1, username="testuser", current_room_id=room_id, preferred_language="en")
        room = Room(id=room_id, name="Test Room")

        expected_messages = [AsyncMock(), AsyncMock()]
        expected_count = 50

        # Mock room exists and user is in room
        mock_repositories.room_repo.get_by_id.return_value = room
        # Mock messages
        mock_repositories.message_repo.get_room_messages.return_value = (expected_messages, expected_count)

        # Act
        messages, count = await room_service.get_room_messages(user, room_id)

        # Assert
        assert messages == expected_messages
        assert count == expected_count
        mock_repositories.message_repo.get_room_messages.assert_called_once()

    async def test_get_room_messages_user_not_in_room(self, room_service, mock_repositories):
        """Test getting messages when user is not in room."""
        # Arrange
        room_id = 5
        user = User(id=1, username="testuser", current_room_id=999)  # Different room
        room = Room(id=room_id, name="Test Room")

        # Mock room exists
        mock_repositories.room_repo.get_by_id.return_value = room

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await room_service.get_room_messages(user, room_id)

        assert exc_info.value.status_code == 403
        assert "must join the room" in str(exc_info.value.detail)