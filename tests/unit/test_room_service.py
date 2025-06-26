from datetime import datetime
import pytest
from unittest.mock import Mock
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.room import Room
from app.models.conversation import Conversation, ConversationType


@pytest.mark.unit
class TestRoomService:
    """Unit Tests for RoomService"""

    def test_create_room_success(self, room_service, mock_repositories):
        """Test: Successfully create a new room."""
        expected_room = Room(id=1, name="New Room", description="Test", max_users=10)
        mock_repositories["room_repo"].name_exists.return_value = False
        mock_repositories["room_repo"].create.return_value = expected_room

        result = room_service.create_room("New Room", "Test", 10)

        assert result == expected_room
        mock_repositories["room_repo"].name_exists.assert_called_once_with("New Room")
        mock_repositories["room_repo"].create.assert_called_once()

    def test_create_room_name_already_exists(self, room_service, mock_repositories):
        """Test: Error when room name already exists."""
        mock_repositories["room_repo"].name_exists.return_value = True

        with pytest.raises(HTTPException) as exc_info:
            room_service.create_room("Existing Room", "Test", 10)

        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value.detail)

    # =====================================
    # DELETE ROOM TESTS
    # =====================================

    def test_delete_room_success_with_cleanup(
        self, room_service, mock_repositories, sample_room
    ):
        """Test: Successfully delete room with proper cleanup."""
        user1 = User(
            id=1,
            username="user1",
            current_room_id=1,
            status=UserStatus.AVAILABLE,
            last_active=datetime.now(),
        )
        user2 = User(
            id=2,
            username="user2",
            current_room_id=1,
            status=UserStatus.BUSY,
            last_active=datetime.now(),
        )
        conversation1 = Conversation(id=1, room_id=1, is_active=True)
        conversation2 = Conversation(id=2, room_id=1, is_active=True)

        mock_repositories["room_repo"].get_by_id.return_value = sample_room
        mock_repositories["room_repo"].get_users_in_room.return_value = [user1, user2]
        mock_repositories["conversation_repo"].get_room_conversations.return_value = [
            conversation1,
            conversation2,
        ]

        result = room_service.delete_room(1)

        assert result["message"] == "Room 'Test Room' has been closed"
        assert result["users_kicked"] == 2
        assert result["conversations_archived"] == 2
        assert "Chat history remains accessible" in result["note"]

        assert user1.current_room_id is None
        assert user1.status == UserStatus.AWAY
        assert user2.current_room_id is None
        assert user2.status == UserStatus.AWAY

        assert conversation1.is_active is False
        assert conversation2.is_active is False

        mock_repositories["room_repo"].soft_delete.assert_called_once_with(1)
        assert mock_repositories["user_repo"].update.call_count == 2
        assert mock_repositories["conversation_repo"].update.call_count == 2

    def test_delete_room_not_found(self, room_service, mock_repositories):
        """Test: Error when room does not exist."""
        mock_repositories["room_repo"].get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            room_service.delete_room(999)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)

    def test_delete_room_no_users_no_conversations(
        self, room_service, mock_repositories, sample_room
    ):
        """Test: Delete empty room with no users or conversations."""
        mock_repositories["room_repo"].get_by_id.return_value = sample_room
        mock_repositories["room_repo"].get_users_in_room.return_value = []
        mock_repositories["conversation_repo"].get_room_conversations.return_value = []

        result = room_service.delete_room(1)

        assert result["users_kicked"] == 0
        assert result["conversations_archived"] == 0
        mock_repositories["room_repo"].soft_delete.assert_called_once_with(1)
        mock_repositories["user_repo"].update.assert_not_called()
        mock_repositories["conversation_repo"].update.assert_not_called()

    # =====================================
    # JOIN ROOM TESTS
    # =====================================

    def test_join_room_success(
        self, room_service, mock_repositories, sample_room, sample_user
    ):
        """Test: Successfully join a room."""
        mock_repositories["room_repo"].get_by_id.return_value = sample_room
        mock_repositories["room_repo"].get_user_count.side_effect = [
            0,
            1,
        ]  # Before and after

        result = room_service.join_room(sample_user, 1)

        assert result["message"] == "Successfully joined room 'Test Room'"
        assert result["user_count"] == 1
        assert sample_user.current_room_id == 1
        assert sample_user.status == UserStatus.AVAILABLE
        mock_repositories["user_repo"].update.assert_called_once_with(sample_user)

    def test_join_room_at_capacity(
        self, room_service, mock_repositories, sample_room, sample_user
    ):
        """Test: Error when room is at full capacity."""
        sample_room.max_users = 2
        mock_repositories["room_repo"].get_by_id.return_value = sample_room
        mock_repositories["room_repo"].get_user_count.return_value = 2

        with pytest.raises(HTTPException) as exc_info:
            room_service.join_room(sample_user, 1)

        assert exc_info.value.status_code == 409
        assert "full" in str(exc_info.value.detail)

    def test_join_room_not_found(self, room_service, mock_repositories, sample_user):
        """Test: Error when room does not exist."""
        mock_repositories["room_repo"].get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            room_service.join_room(sample_user, 999)

        assert exc_info.value.status_code == 404

    # =====================================
    # LEAVE ROOM TESTS
    # =====================================

    def test_leave_room_success(
        self, room_service, mock_repositories, sample_room, sample_user
    ):
        """Test: Successfully leave a room."""
        sample_user.current_room_id = 1
        mock_repositories["room_repo"].get_by_id.return_value = sample_room

        result = room_service.leave_room(sample_user, 1)

        assert result["message"] == "Left room 'Test Room'"
        assert sample_user.current_room_id is None
        assert sample_user.status == UserStatus.AWAY
        mock_repositories["user_repo"].update.assert_called_once_with(sample_user)

    def test_leave_room_not_in_room(
        self, room_service, mock_repositories, sample_room, sample_user
    ):
        """Test: Error when user is not in the room."""
        sample_user.current_room_id = 2
        mock_repositories["room_repo"].get_by_id.return_value = sample_room

        with pytest.raises(HTTPException) as exc_info:
            room_service.leave_room(sample_user, 1)

        assert exc_info.value.status_code == 400
        assert "not in room" in str(exc_info.value.detail)

    # =====================================
    # UPDATE ROOM TESTS
    # =====================================

    def test_update_room_success(self, room_service, mock_repositories, sample_room):
        """Test: Successfully update room."""
        mock_repositories["room_repo"].get_by_id.return_value = sample_room
        mock_repositories["room_repo"].name_exists.return_value = False
        mock_repositories["room_repo"].update.return_value = sample_room

        result = room_service.update_room(1, "Updated Room", "New description", 10)

        assert sample_room.name == "Updated Room"
        assert sample_room.description == "New description"
        assert sample_room.max_users == 10
        mock_repositories["room_repo"].update.assert_called_once_with(sample_room)

    def test_update_room_name_conflict(
        self, room_service, mock_repositories, sample_room
    ):
        """Test: Error when updating to existing room name."""
        mock_repositories["room_repo"].get_by_id.return_value = sample_room
        mock_repositories["room_repo"].name_exists.return_value = True

        with pytest.raises(HTTPException) as exc_info:
            room_service.update_room(1, "Existing Name", "Description", 5)

        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value.detail)

    # =====================================
    # GET ROOM USERS TESTS
    # =====================================

    def test_get_room_users_success(self, room_service, mock_repositories, sample_room):
        """Test: Successfully get users in room."""
        users = [
            User(
                id=1,
                username="user1",
                status=UserStatus.AVAILABLE,
                last_active=datetime.now(),
            ),
            User(
                id=2,
                username="user2",
                status=UserStatus.BUSY,
                last_active=datetime.now(),
            ),
        ]
        mock_repositories["room_repo"].get_by_id.return_value = sample_room
        mock_repositories["room_repo"].get_users_in_room.return_value = users

        result = room_service.get_room_users(1)

        assert result["room_id"] == 1
        assert result["room_name"] == "Test Room"
        assert result["total_users"] == 2
        assert len(result["users"]) == 2


if __name__ == "__main__":
    print("Unit Tests for RoomService, tests/unit/test_room_service.py")
