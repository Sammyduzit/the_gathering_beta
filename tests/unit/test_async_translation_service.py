import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from app.services.translation_service import TranslationService
from app.models.message import Message
from app.models.message_translation import MessageTranslation

# Import async fixtures
from tests.async_conftest import (
    async_translation_service,
    async_mock_repositories,
)


@pytest.mark.asyncio
class TestAsyncTranslationService:
    """Async unit tests for TranslationService."""

    async def test_translate_message_content_success(self, async_translation_service):
        """Test successful message translation."""
        # Arrange
        content = "Hello world"
        target_languages = ["de"]
        expected_translation = {"de": "Hallo Welt"}

        with patch('app.services.translation_service.asyncio.get_event_loop') as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.return_value = type('MockResult', (), {'text': 'Hallo Welt'})()
            mock_loop.return_value.run_in_executor = mock_executor

            # Act
            result = await async_translation_service.translate_message_content(
                content=content,
                target_languages=target_languages,
                source_language="en"
            )

            # Assert
            assert result == expected_translation
            mock_executor.assert_called_once()

    async def test_translate_message_content_empty_content(self, async_translation_service):
        """Test translation with empty content."""
        # Act
        result = await async_translation_service.translate_message_content(
            content="",
            target_languages=["de"],
            source_language="en"
        )

        # Assert
        assert result == {}

    async def test_translate_message_content_invalid_language(self, async_translation_service):
        """Test translation with invalid target language."""
        # Act
        result = await async_translation_service.translate_message_content(
            content="Hello",
            target_languages=["invalid_lang"],
            source_language="en"
        )

        # Assert - Should handle gracefully and return empty dict
        assert result == {}

    async def test_translate_multiple_languages_success(self, async_translation_service):
        """Test translation to multiple languages."""
        # Arrange
        content = "Hello"
        target_languages = ["de", "fr", "es"]

        with patch('app.services.translation_service.asyncio.get_event_loop') as mock_loop:
            mock_executor = AsyncMock()
            # Mock different translations for each language
            mock_executor.side_effect = [
                type('MockResult', (), {'text': 'Hallo'})(),
                type('MockResult', (), {'text': 'Bonjour'})(),
                type('MockResult', (), {'text': 'Hola'})(),
            ]
            mock_loop.return_value.run_in_executor = mock_executor

            # Act - Use the correct method name
            result = await async_translation_service.translate_message_content(
                content=content,
                target_languages=target_languages,
                source_language="en"
            )

            # Assert
            expected = {
                "de": "Hallo",
                "fr": "Bonjour",
                "es": "Hola"
            }
            assert result == expected
            assert mock_executor.call_count == 3

    async def test_translate_multiple_languages_empty_list(self, async_translation_service):
        """Test translation with empty target languages list."""
        # Act
        result = await async_translation_service.translate_message_content(
            content="Hello",
            target_languages=[],
            source_language="en"
        )

        # Assert
        assert result == {}

    async def test_get_existing_translation_found(self, async_translation_service, async_mock_repositories):
        """Test retrieving existing translation when found."""
        # Arrange
        message_id = 1
        target_language = "de"
        expected_translation = "Hallo Welt"

        # Create mock translation object
        mock_translation = MessageTranslation(
            message_id=message_id,
            content=expected_translation,
            target_language=target_language
        )
        async_mock_repositories["translation_repo"].get_by_message_and_language.return_value = mock_translation

        # Act
        result = await async_translation_service.get_message_translation(
            message_id=message_id,
            target_language=target_language
        )

        # Assert
        assert result == expected_translation

    async def test_get_existing_translation_not_found(self, async_translation_service, async_mock_repositories):
        """Test retrieving existing translation when not found."""
        # Arrange
        async_mock_repositories["translation_repo"].get_by_message_and_language.return_value = None

        # Act
        result = await async_translation_service.get_message_translation(
            message_id=1,
            target_language="de"
        )

        # Assert
        assert result is None

    async def test_translate_and_store_message_success(self, async_translation_service, async_mock_repositories):
        """Test translate and store message successfully."""
        # Arrange
        message_id = 1
        content = "Hello world"
        target_languages = ["de", "fr"]

        # Mock successful translation result
        expected_translations = {"de": "Hallo Welt", "fr": "Bonjour le monde"}

        with patch.object(async_translation_service, 'translate_message_content', return_value=expected_translations):
            # Mock create_message_translations to return list of MessageTranslation objects
            mock_translation_objects = [
                MessageTranslation(message_id=message_id, content="Hallo Welt", target_language="de"),
                MessageTranslation(message_id=message_id, content="Bonjour le monde", target_language="fr")
            ]
            with patch.object(async_translation_service, 'create_message_translations', return_value=mock_translation_objects):
                # Act
                result = await async_translation_service.translate_and_store_message(
                    message_id=message_id,
                    content=content,
                    target_languages=target_languages
                )

                # Assert
                assert result == 2  # Number of translations created