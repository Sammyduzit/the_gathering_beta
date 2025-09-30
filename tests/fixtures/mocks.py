"""
Centralized mock services and repositories for unit testing.

This module provides reusable mock objects with sensible defaults,
making unit tests faster and more predictable by avoiding real
database operations and external service calls.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, Mock

from app.models.conversation import Conversation, ConversationType
from app.models.message import Message
from app.models.room import Room
from app.models.user import User, UserStatus


class MockRepositories:
    """Container for all repository mocks with consistent behavior."""

    def __init__(self):
        self.user_repo = AsyncMock()
        self.room_repo = AsyncMock()
        self.conversation_repo = AsyncMock()
        self.message_repo = AsyncMock()
        self.translation_repo = AsyncMock()

        # Setup default behaviors
        self._setup_user_repo()
        self._setup_room_repo()
        self._setup_conversation_repo()
        self._setup_message_repo()
        self._setup_translation_repo()

    def _setup_user_repo(self):
        """Setup default behaviors for user repository mock."""
        # Default user for common operations
        default_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            is_admin=False,
            status=UserStatus.AVAILABLE,
            last_active=datetime.now(),
        )

        # Common method behaviors
        self.user_repo.get_by_id.return_value = default_user
        self.user_repo.get_by_email.return_value = default_user
        self.user_repo.get_by_username.return_value = default_user
        self.user_repo.create.return_value = default_user
        self.user_repo.update.return_value = default_user
        self.user_repo.delete.return_value = True
        self.user_repo.get_all_active.return_value = [default_user]
        self.user_repo.get_users_in_room.return_value = [default_user]

    def _setup_room_repo(self):
        """Setup default behaviors for room repository mock."""
        default_room = Room(
            id=1,
            name="Test Room",
            description="Test room description",
            max_users=10,
            is_active=True,
            is_translation_enabled=True,
            created_at=datetime.now(),
        )

        self.room_repo.get_by_id.return_value = default_room
        self.room_repo.get_by_name.return_value = default_room
        self.room_repo.create.return_value = default_room
        self.room_repo.update.return_value = default_room
        self.room_repo.delete.return_value = True
        self.room_repo.get_all_active.return_value = [default_room]
        self.room_repo.get_user_count.return_value = 1

    def _setup_conversation_repo(self):
        """Setup default behaviors for conversation repository mock."""
        default_conversation = Conversation(
            id=1,
            conversation_type=ConversationType.PRIVATE,
            max_participants=2,
            is_active=True,
            created_at=datetime.now(),
        )

        self.conversation_repo.get_by_id.return_value = default_conversation
        self.conversation_repo.create.return_value = default_conversation
        self.conversation_repo.update.return_value = default_conversation
        self.conversation_repo.delete.return_value = True
        self.conversation_repo.get_user_conversations.return_value = [default_conversation]
        self.conversation_repo.get_conversation_participants.return_value = []

    def _setup_message_repo(self):
        """Setup default behaviors for message repository mock."""
        default_message = Message(
            id=1,
            content="Test message",
            sender_id=1,
            room_id=1,
            sent_at=datetime.now(),
        )

        self.message_repo.get_by_id.return_value = default_message
        self.message_repo.create.return_value = default_message
        self.message_repo.update.return_value = default_message
        self.message_repo.delete.return_value = True
        self.message_repo.get_room_messages.return_value = [default_message]
        self.message_repo.get_conversation_messages.return_value = [default_message]
        self.message_repo.get_recent_messages.return_value = [default_message]

    def _setup_translation_repo(self):
        """Setup default behaviors for translation repository mock."""
        self.translation_repo.create_translation.return_value = None
        self.translation_repo.get_translation.return_value = None
        self.translation_repo.get_message_translations.return_value = {}
        self.translation_repo.delete_message_translations.return_value = 0

    def reset_all(self):
        """Reset all mocks to their default state."""
        for repo in [
            self.user_repo,
            self.room_repo,
            self.conversation_repo,
            self.message_repo,
            self.translation_repo
        ]:
            repo.reset_mock()

        # Restore default behaviors
        self._setup_user_repo()
        self._setup_room_repo()
        self._setup_conversation_repo()
        self._setup_message_repo()
        self._setup_translation_repo()


class MockServices:
    """Container for all service mocks with consistent behavior."""

    def __init__(self):
        self.translation_service = AsyncMock()
        self.room_service = AsyncMock()
        self.conversation_service = AsyncMock()
        self.background_service = AsyncMock()

        # Setup default behaviors
        self._setup_translation_service()
        self._setup_room_service()
        self._setup_conversation_service()
        self._setup_background_service()

    def _setup_translation_service(self):
        """Setup default behaviors for translation service mock."""
        self.translation_service.translate_message_content.return_value = {}
        self.translation_service.get_message_translation.return_value = None
        self.translation_service.translate_and_store_message.return_value = 0
        self.translation_service.create_message_translations.return_value = []
        self.translation_service.get_all_message_translations.return_value = {}
        self.translation_service.delete_message_translations.return_value = 0

    def _setup_room_service(self):
        """Setup default behaviors for room service mock."""
        default_room = Room(
            id=1,
            name="Test Room",
            description="Test room description",
            max_users=10,
            is_active=True,
        )

        self.room_service.create_room.return_value = default_room
        self.room_service.get_room.return_value = default_room
        self.room_service.update_room.return_value = default_room
        self.room_service.delete_room.return_value = True
        self.room_service.join_room.return_value = True
        self.room_service.leave_room.return_value = True
        self.room_service.send_message.return_value = Message(
            id=1, content="Test message", sender_id=1, room_id=1
        )

    def _setup_conversation_service(self):
        """Setup default behaviors for conversation service mock."""
        default_conversation = Conversation(
            id=1,
            conversation_type=ConversationType.PRIVATE,
            max_participants=2,
            is_active=True,
        )

        self.conversation_service.create_conversation.return_value = default_conversation
        self.conversation_service.get_conversation.return_value = default_conversation
        self.conversation_service.send_message.return_value = Message(
            id=1, content="Test message", sender_id=1, conversation_id=1
        )
        self.conversation_service.add_participant.return_value = True
        self.conversation_service.remove_participant.return_value = True

    def _setup_background_service(self):
        """Setup default behaviors for background service mock."""
        self.background_service.process_translation_queue.return_value = 0
        self.background_service.cleanup_old_translations.return_value = 0
        self.background_service.update_user_activity.return_value = None

    def reset_all(self):
        """Reset all service mocks to their default state."""
        for service in [
            self.translation_service,
            self.room_service,
            self.conversation_service,
            self.background_service
        ]:
            service.reset_mock()

        # Restore default behaviors
        self._setup_translation_service()
        self._setup_room_service()
        self._setup_conversation_service()
        self._setup_background_service()


class MockDatabase:
    """Mock database session for unit testing."""

    def __init__(self):
        self.session = AsyncMock()
        self.setup_session_behavior()

    def setup_session_behavior(self):
        """Setup realistic session behavior."""
        self.session.add.return_value = None
        self.session.commit.return_value = None
        self.session.rollback.return_value = None
        self.session.refresh.return_value = None
        self.session.flush.return_value = None
        self.session.close.return_value = None

        # Mock query behavior
        self.session.execute.return_value = AsyncMock()
        self.session.scalar.return_value = None
        self.session.scalars.return_value = AsyncMock()

    def reset(self):
        """Reset session mock."""
        self.session.reset_mock()
        self.setup_session_behavior()


class MockFastAPI:
    """Mock FastAPI components for API testing."""

    def __init__(self):
        self.background_tasks = Mock()
        self.request = Mock()
        self.response = Mock()

        self.setup_background_tasks()
        self.setup_request()
        self.setup_response()

    def setup_background_tasks(self):
        """Setup background tasks mock."""
        self.background_tasks.add_task.return_value = None

    def setup_request(self):
        """Setup request mock."""
        self.request.client.host = "127.0.0.1"
        self.request.headers = {}
        self.request.method = "GET"
        self.request.url.path = "/test"

    def setup_response(self):
        """Setup response mock."""
        self.response.status_code = 200
        self.response.headers = {}

    def reset_all(self):
        """Reset all FastAPI mocks."""
        self.background_tasks.reset_mock()
        self.request.reset_mock()
        self.response.reset_mock()

        self.setup_background_tasks()
        self.setup_request()
        self.setup_response()


# Convenience functions for common mock scenarios
def create_mock_dependencies() -> Dict[str, Any]:
    """Create complete set of mocked dependencies."""
    repos = MockRepositories()
    services = MockServices()
    database = MockDatabase()
    fastapi = MockFastAPI()

    return {
        "repositories": repos,
        "services": services,
        "database": database,
        "fastapi": fastapi,
    }


def create_mock_user_scenario(user_id: int = 1) -> Dict[str, Any]:
    """Create mock scenario focused on user operations."""
    user = User(
        id=user_id,
        username=f"user{user_id}",
        email=f"user{user_id}@example.com",
        is_admin=False,
        status=UserStatus.AVAILABLE,
    )

    repos = MockRepositories()
    repos.user_repo.get_by_id.return_value = user
    repos.user_repo.get_by_email.return_value = user

    return {
        "user": user,
        "repositories": repos,
    }


def create_mock_room_scenario(room_id: int = 1) -> Dict[str, Any]:
    """Create mock scenario focused on room operations."""
    room = Room(
        id=room_id,
        name=f"Test Room {room_id}",
        description="Test room description",
        max_users=10,
        is_active=True,
    )

    repos = MockRepositories()
    repos.room_repo.get_by_id.return_value = room

    return {
        "room": room,
        "repositories": repos,
    }


def create_mock_error_scenario() -> Dict[str, Any]:
    """Create mock scenario that simulates errors."""
    repos = MockRepositories()

    # Configure repositories to raise exceptions
    repos.user_repo.get_by_id.side_effect = Exception("Database error")
    repos.room_repo.create.side_effect = Exception("Constraint violation")

    services = MockServices()
    services.translation_service.translate_message_content.side_effect = Exception("API error")

    return {
        "repositories": repos,
        "services": services,
    }