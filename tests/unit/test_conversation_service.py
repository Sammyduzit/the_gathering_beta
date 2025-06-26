import pytest
from unittest.mock import Mock
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.conversation import Conversation, ConversationType
from app.models.message import Message, MessageType


@pytest.mark.unit
class TestConversationService:
    """Unit tests for ConversationService."""

    def test_create_private_conversation_success(
        self, conversation_service, mock_repositories, sample_user
    ):
        """Test: Successfully create private conversation."""
        other_user = User(id=2, username="otheruser", current_room_id=1, is_active=True)
        expected_conversation = Conversation(
            id=1, room_id=1, conversation_type=ConversationType.PRIVATE
        )

        mock_repositories["user_repo"].get_by_username.return_value = other_user
        mock_repositories[
            "conversation_repo"
        ].create_private_conversation.return_value = expected_conversation

        result = conversation_service.create_conversation(
            current_user=sample_user,
            participant_usernames=["otheruser"],
            conversation_type="private",
        )

        assert result == expected_conversation
        mock_repositories["user_repo"].get_by_username.assert_called_once_with(
            "otheruser"
        )
        mock_repositories[
            "conversation_repo"
        ].create_private_conversation.assert_called_once_with(
            room_id=1, participant_ids=[1, 2]
        )

    def test_create_conversation_user_not_in_room(
        self, conversation_service, sample_user
    ):
        """Test: Error when user is not in a room."""
        sample_user.current_room_id = None

        with pytest.raises(HTTPException) as exc_info:
            conversation_service.create_conversation(
                current_user=sample_user,
                participant_usernames=["otheruser"],
                conversation_type="private",
            )

        assert exc_info.value.status_code == 403
        assert "User must be in a room" in str(exc_info.value.detail)

    def test_create_private_conversation_wrong_participant_count(
        self, conversation_service, sample_user
    ):
        """Test: Private conversation requires exactly 1 other participant."""

        with pytest.raises(HTTPException) as exc_info:
            conversation_service.create_conversation(
                current_user=sample_user,
                participant_usernames=["user1", "user2"],
                conversation_type="private",
            )

        assert exc_info.value.status_code == 400
        assert "exactly 1 other participant" in str(exc_info.value.detail)

    def test_create_conversation_participant_not_found(
        self, conversation_service, mock_repositories, sample_user
    ):
        """Test: Error when participant does not exist."""
        mock_repositories["user_repo"].get_by_username.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            conversation_service.create_conversation(
                current_user=sample_user,
                participant_usernames=["nonexistent"],
                conversation_type="private",
            )

        assert exc_info.value.status_code == 400
        assert "not found" in str(exc_info.value.detail)

    # =====================================
    # SEND MESSAGE TESTS
    # =====================================

    def test_send_message_success(
        self, conversation_service, mock_repositories, sample_user, sample_conversation
    ):
        """Test: Successfully send a message."""
        expected_message = Message(
            id=1,
            sender_id=1,
            content="Hello!",
            conversation_id=1,
            message_type=MessageType.TEXT,
        )

        mock_repositories[
            "conversation_repo"
        ].get_by_id.return_value = sample_conversation
        mock_repositories["conversation_repo"].is_participant.return_value = True
        mock_repositories[
            "message_repo"
        ].create_conversation_message.return_value = expected_message

        result = conversation_service.send_message(
            current_user=sample_user, conversation_id=1, content="Hello!"
        )

        assert result.content == "Hello!"
        assert result.sender_username == "testuser"
        mock_repositories["conversation_repo"].is_participant.assert_called_once_with(
            1, 1
        )
        mock_repositories[
            "message_repo"
        ].create_conversation_message.assert_called_once_with(
            sender_id=1, conversation_id=1, content="Hello!"
        )

    def test_send_message_conversation_not_found(
        self, conversation_service, mock_repositories, sample_user
    ):
        """Test: Error when conversation does not exist."""
        mock_repositories["conversation_repo"].get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            conversation_service.send_message(
                current_user=sample_user, conversation_id=999, content="Hello!"
            )

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)

    def test_send_message_not_participant(
        self, conversation_service, mock_repositories, sample_user, sample_conversation
    ):
        """Test: Error when user is not a participant in the conversation."""
        mock_repositories[
            "conversation_repo"
        ].get_by_id.return_value = sample_conversation
        mock_repositories["conversation_repo"].is_participant.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            conversation_service.send_message(
                current_user=sample_user, conversation_id=1, content="Hello!"
            )

        assert exc_info.value.status_code == 403
        assert "not a participant" in str(exc_info.value.detail)


if __name__ == "__main__":
    print("Unit Tests für ConversationService, tests/unit/test_conversation_service.py")
