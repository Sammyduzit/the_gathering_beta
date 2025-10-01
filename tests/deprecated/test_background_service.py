"""
Clean unit tests for BackgroundService using dependency injection.

Tests demonstrate proper service testing with mocked dependencies,
factory pattern for test data, and no external patches.
"""

from unittest.mock import AsyncMock

import pytest

from app.interfaces.translator import TranslationError
from app.models.message_translation import MessageTranslation


@pytest.mark.unit
class TestBackgroundService:
    """Unit tests for BackgroundService with clean dependency injection."""

    async def test_process_message_translation_background_success(
        self, mock_repositories
    ):
        """Test successful background message translation processing."""
        # Arrange
        from app.models.message import Message
        from app.services.background_service import BackgroundService

        message = Message(id=1, content="Hello world", sender_id=1)
        target_languages = ["de", "fr"]
        room_translation_enabled = True

        # Mock translation service
        mock_translation_service = AsyncMock()
        mock_translation_service.translate_message_content.return_value = {
            "de": "Hallo Welt",
            "fr": "Bonjour le monde"
        }

        # Create service with mocked translation service
        background_service = BackgroundService(
            translation_service=mock_translation_service,
            message_translation_repo=mock_repositories.translation_repo,
        )

        # Mock no existing translation
        mock_repositories.translation_repo.get_by_message_and_language.return_value = None

        # Mock repository create
        mock_repositories.translation_repo.create.return_value = AsyncMock()

        # Act
        result = await background_service.process_message_translation_background(
            message=message,
            target_languages=target_languages,
            room_translation_enabled=room_translation_enabled,
        )

        # Assert
        assert len(result) == 2
        assert result["de"] == "Hallo Welt"
        assert result["fr"] == "Bonjour le monde"

        # Verify translation service was called for each language
        assert mock_translation_service.translate_message_content.call_count == 2

        # Verify storage was called for each successful translation
        assert mock_repositories.translation_repo.create.call_count == 2

    async def test_process_message_translation_background_disabled(
        self, background_service
    ):
        """Test background translation when room translation is disabled."""
        # Arrange
        from app.models.message import Message
        message = Message(id=2, content="Hello world", sender_id=1)

        target_languages = ["de", "fr"]
        room_translation_enabled = False

        # Act
        result = await background_service.process_message_translation_background(
            message=message,
            target_languages=target_languages,
            room_translation_enabled=room_translation_enabled,
        )

        # Assert
        assert result == {}

    async def test_process_message_translation_background_existing_translation(
        self, mock_repositories
    ):
        """Test background translation when translation already exists."""
        # Arrange
        from app.models.message import Message
        from app.services.background_service import BackgroundService

        message = Message(id=3, content="Hello world", sender_id=1)
        target_languages = ["de"]
        room_translation_enabled = True

        # Mock translation service
        mock_translation_service = AsyncMock()

        # Create service with mocked translation service
        background_service = BackgroundService(
            translation_service=mock_translation_service,
            message_translation_repo=mock_repositories.translation_repo,
        )

        # Mock existing translation found
        existing_translation = MessageTranslation(
            message_id=message.id,
            content="Existing Hallo",
            target_language="de"
        )
        mock_repositories.translation_repo.get_by_message_and_language.return_value = existing_translation

        # Act
        result = await background_service.process_message_translation_background(
            message=message,
            target_languages=target_languages,
            room_translation_enabled=room_translation_enabled,
        )

        # Assert
        assert result["de"] == "Existing Hallo"

        # Verify translation service was NOT called
        mock_translation_service.translate_message_content.assert_not_called()

    async def test_process_message_translation_background_translation_error(
        self, mock_repositories
    ):
        """Test background translation handling translation service failure."""
        # Arrange
        from app.models.message import Message
        from app.services.background_service import BackgroundService

        message = Message(id=4, content="Hello world", sender_id=1)
        target_languages = ["de", "fr"]
        room_translation_enabled = True

        # Mock translation service
        mock_translation_service = AsyncMock()

        # Mock translation service failure for first language, success for second
        def side_effect(content, target_languages, source_language):
            if target_languages == ["de"]:
                raise TranslationError("Translation API error")
            return {"fr": "Bonjour"}

        mock_translation_service.translate_message_content.side_effect = side_effect

        # Create service with mocked translation service
        background_service = BackgroundService(
            translation_service=mock_translation_service,
            message_translation_repo=mock_repositories.translation_repo,
        )

        # Mock no existing translation
        mock_repositories.translation_repo.get_by_message_and_language.return_value = None

        # Act
        result = await background_service.process_message_translation_background(
            message=message,
            target_languages=target_languages,
            room_translation_enabled=room_translation_enabled,
        )

        # Assert
        assert len(result) == 1
        assert "fr" in result
        assert "de" not in result

    async def test_process_message_translation_background_empty_languages(
        self, background_service
    ):
        """Test background translation with empty target languages."""
        # Arrange
        from app.models.message import Message
        message = Message(id=5, content="Hello world", sender_id=1)

        target_languages = []
        room_translation_enabled = True

        # Act
        result = await background_service.process_message_translation_background(
            message=message,
            target_languages=target_languages,
            room_translation_enabled=room_translation_enabled,
        )

        # Assert
        assert result == {}

    async def test_cleanup_old_translations_background_success(self, background_service):
        """Test successful old translations cleanup."""
        # Arrange
        days_old = 30

        # Act
        result = await background_service.cleanup_old_translations_background(days_old=days_old)

        # Assert
        assert result == 0  # Placeholder implementation returns 0

    async def test_log_user_activity_background_success(self, background_service):
        """Test successful user activity logging."""
        # Arrange
        user_id = 1
        activity_type = "message_sent"
        details = {"room_id": 1, "message_length": 10}

        # Act
        result = await background_service.log_user_activity_background(
            user_id=user_id, activity_type=activity_type, details=details
        )

        # Assert
        assert result is None

    async def test_log_user_activity_background_without_details(self, background_service):
        """Test user activity logging without details."""
        # Arrange
        user_id = 1
        activity_type = "room_joined"

        # Act
        result = await background_service.log_user_activity_background(
            user_id=user_id, activity_type=activity_type
        )

        # Assert
        assert result is None

    async def test_notify_room_users_background_success(self, background_service):
        """Test successful room user notification."""
        # Arrange
        room_id = 1
        message = "User joined the room"
        exclude_user_ids = [2, 3]

        # Act
        result = await background_service.notify_room_users_background(
            room_id=room_id, message=message, exclude_user_ids=exclude_user_ids
        )

        # Assert
        assert result is None

    async def test_notify_room_users_background_no_exclusions(self, background_service):
        """Test room user notification without exclusions."""
        # Arrange
        room_id = 1
        message = "Room announcement"

        # Act
        result = await background_service.notify_room_users_background(
            room_id=room_id, message=message
        )

        # Assert
        assert result is None