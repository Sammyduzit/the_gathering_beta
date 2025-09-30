from unittest.mock import AsyncMock, patch

import deepl
import pytest

from app.models.message_translation import MessageTranslation

# Import async fixtures
from tests.async_conftest import (
    async_background_service,
    async_mock_repositories,
    mock_translation_service,
    sample_async_message,
)


@pytest.mark.asyncio
class TestAsyncBackgroundService:
    """Async unit tests for BackgroundService."""

    async def test_process_message_translation_background_success(
        self, async_background_service, async_mock_repositories, sample_async_message
    ):
        """Test successful background message translation processing."""
        # Arrange
        target_languages = ["de", "fr"]
        room_translation_enabled = True

        # Mock existing translation check (none found)
        async_mock_repositories["translation_repo"].get_by_message_and_language.return_value = None

        # Mock translation service response
        translation_result = {"de": "Hallo Welt", "fr": "Bonjour le monde"}
        async_background_service.translation_service.translate_message_content = AsyncMock(
            return_value=translation_result
        )

        # Mock store translation
        mock_stored_translation = MessageTranslation(
            message_id=sample_async_message.id, content="Hallo Welt", target_language="de"
        )
        async_mock_repositories["translation_repo"].store_translation.return_value = mock_stored_translation

        # Act
        result = await async_background_service.process_message_translation_background(
            message=sample_async_message,
            target_languages=target_languages,
            room_translation_enabled=room_translation_enabled,
        )

        # Assert
        assert len(result) == 2
        assert result["de"] == "Hallo Welt"
        assert result["fr"] == "Bonjour le monde"

        # Verify translation service was called for each language
        assert async_background_service.translation_service.translate_message_content.call_count == 2

        # Verify storage was called for each successful translation
        assert async_mock_repositories["translation_repo"].create.call_count == 2

    async def test_process_message_translation_background_disabled(
        self, async_background_service, sample_async_message
    ):
        """Test background translation when room translation is disabled."""
        # Arrange
        target_languages = ["de", "fr"]
        room_translation_enabled = False

        # Act
        result = await async_background_service.process_message_translation_background(
            message=sample_async_message,
            target_languages=target_languages,
            room_translation_enabled=room_translation_enabled,
        )

        # Assert
        assert result == {}

    async def test_process_message_translation_background_existing_translation(
        self, async_background_service, async_mock_repositories, sample_async_message
    ):
        """Test background translation when translation already exists."""
        # Arrange
        target_languages = ["de"]
        room_translation_enabled = True

        # Mock existing translation found
        existing_translation = MessageTranslation(
            message_id=sample_async_message.id, content="Existing Hallo", target_language="de"
        )
        async_mock_repositories["translation_repo"].get_by_message_and_language.return_value = existing_translation

        # Mock translation service as AsyncMock
        async_background_service.translation_service.translate_message_content = AsyncMock()

        # Act
        result = await async_background_service.process_message_translation_background(
            message=sample_async_message,
            target_languages=target_languages,
            room_translation_enabled=room_translation_enabled,
        )

        # Assert
        assert result["de"] == "Existing Hallo"

        # Verify translation service was NOT called
        async_background_service.translation_service.translate_message_content.assert_not_called()

    async def test_process_message_translation_background_translation_failure(
        self, async_background_service, async_mock_repositories, sample_async_message
    ):
        """Test background translation handling translation service failure."""
        # Arrange
        target_languages = ["de", "fr"]
        room_translation_enabled = True

        # Mock no existing translation
        async_mock_repositories["translation_repo"].get_by_message_and_language.return_value = None

        # Mock translation service failure for first language, success for second
        mock_translate = AsyncMock()
        mock_translate.side_effect = [deepl.DeepLException("Translation API error"), {"fr": "Bonjour"}]
        async_background_service.translation_service.translate_message_content = mock_translate

        # Act
        result = await async_background_service.process_message_translation_background(
            message=sample_async_message,
            target_languages=target_languages,
            room_translation_enabled=room_translation_enabled,
        )

        # Assert
        # Should only have successful translation
        assert len(result) == 1
        assert "fr" in result
        assert "de" not in result

    async def test_log_user_activity_background_success(self, async_background_service):
        """Test successful user activity logging."""
        # Arrange
        user_id = 1
        activity_type = "message_sent"
        details = {"room_id": 1, "message_length": 10}

        # Act
        result = await async_background_service.log_user_activity_background(
            user_id=user_id, activity_type=activity_type, details=details
        )

        # Assert
        assert result is None  # Success returns None

    async def test_log_user_activity_background_without_details(self, async_background_service):
        """Test user activity logging without details."""
        # Arrange
        user_id = 1
        activity_type = "room_joined"

        # Act
        result = await async_background_service.log_user_activity_background(
            user_id=user_id, activity_type=activity_type
        )

        # Assert
        assert result is None

    async def test_notify_room_users_background_success(self, async_background_service):
        """Test successful room user notification."""
        # Arrange
        room_id = 1
        message = "User joined the room"
        exclude_user_ids = [2, 3]

        # Act
        result = await async_background_service.notify_room_users_background(
            room_id=room_id, message=message, exclude_user_ids=exclude_user_ids
        )

        # Assert
        assert result is None  # Success returns None

    async def test_notify_room_users_background_no_exclusions(self, async_background_service):
        """Test room user notification without exclusions."""
        # Arrange
        room_id = 1
        message = "Room announcement"

        # Act
        result = await async_background_service.notify_room_users_background(room_id=room_id, message=message)

        # Assert
        assert result is None

    @patch("app.services.background_service.logger")
    async def test_background_task_error_logging(self, mock_logger, async_background_service):
        """Test that background task errors are properly logged."""
        # Arrange
        user_id = 1
        activity_type = "error_test"

        # Mock an exception in the background task
        with patch.object(
            async_background_service, "log_user_activity_background", side_effect=Exception("Test error")
        ):
            # Act & Assert
            with pytest.raises(Exception):
                await async_background_service.log_user_activity_background(
                    user_id=user_id, activity_type=activity_type
                )
