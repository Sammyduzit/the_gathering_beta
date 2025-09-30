"""
Clean unit tests for TranslationService using dependency injection.

These tests demonstrate the proper way to test services after DI refactoring:
- Create real service instances
- Mock only the dependencies (interfaces)
- Test actual business logic
- No patches required!
"""

from unittest.mock import AsyncMock, Mock

import pytest

from app.interfaces.translator import TranslatorInterface, TranslationError
from app.models.message_translation import MessageTranslation
from app.services.translation_service import TranslationService


@pytest.mark.unit
class TestTranslationServiceClean:
    """Clean unit tests for TranslationService with mocked dependencies."""

    @pytest.fixture
    def mock_translator(self):
        """Mock translator implementing TranslatorInterface."""
        mock = AsyncMock(spec=TranslatorInterface)
        return mock

    @pytest.fixture
    def mock_message_repo(self):
        """Mock message repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_translation_repo(self):
        """Mock translation repository."""
        return AsyncMock()

    @pytest.fixture
    def translation_service(self, mock_translator, mock_message_repo, mock_translation_repo):
        """Real TranslationService instance with mocked dependencies."""
        return TranslationService(
            translator=mock_translator,
            message_repo=mock_message_repo,
            translation_repo=mock_translation_repo,
        )

    async def test_translate_message_content_success(self, translation_service, mock_translator):
        """Test successful message translation."""
        # Arrange
        content = "Hello world"
        target_languages = ["de", "fr"]
        expected_translations = {"de": "Hallo Welt", "fr": "Bonjour le monde"}

        mock_translator.translate_to_multiple_languages.return_value = expected_translations

        # Act
        result = await translation_service.translate_message_content(
            content=content,
            target_languages=target_languages,
            source_language="en"
        )

        # Assert
        assert result == expected_translations
        mock_translator.translate_to_multiple_languages.assert_called_once_with(
            text=content,
            target_languages=target_languages,
            source_language="en"
        )

    async def test_translate_message_content_empty_content(self, translation_service):
        """Test translation with empty content returns empty dict."""
        # Act
        result = await translation_service.translate_message_content(
            content="",
            target_languages=["de"]
        )

        # Assert
        assert result == {}

    async def test_translate_message_content_no_target_languages(self, translation_service):
        """Test translation with no target languages returns empty dict."""
        # Act
        result = await translation_service.translate_message_content(
            content="Hello world",
            target_languages=None
        )

        # Assert
        assert result == {}

    async def test_translate_message_content_translation_error(self, translation_service, mock_translator):
        """Test translation service handles TranslationError gracefully."""
        # Arrange
        mock_translator.translate_to_multiple_languages.side_effect = TranslationError("API Error")

        # Act
        result = await translation_service.translate_message_content(
            content="Hello world",
            target_languages=["de"]
        )

        # Assert
        assert result == {}

    async def test_create_message_translations_success(self, translation_service, mock_translation_repo):
        """Test successful creation of translation objects."""
        # Arrange
        message_id = 123
        translations = {"de": "Hallo Welt", "fr": "Bonjour le monde"}

        # Mock repository to return created translations
        expected_objects = [
            MessageTranslation(message_id=123, target_language="de", content="Hallo Welt"),
            MessageTranslation(message_id=123, target_language="fr", content="Bonjour le monde"),
        ]
        mock_translation_repo.bulk_create_translations.return_value = expected_objects

        # Act
        result = await translation_service.create_message_translations(
            message_id=message_id,
            translations=translations
        )

        # Assert
        assert len(result) == 2
        assert result == expected_objects

        # Verify repository was called with correct translation objects
        mock_translation_repo.bulk_create_translations.assert_called_once()
        call_args = mock_translation_repo.bulk_create_translations.call_args[0][0]
        assert len(call_args) == 2

        # Check the translation objects passed to repository
        assert call_args[0].message_id == message_id
        assert call_args[0].target_language == "de"
        assert call_args[0].content == "Hallo Welt"

        assert call_args[1].message_id == message_id
        assert call_args[1].target_language == "fr"
        assert call_args[1].content == "Bonjour le monde"

    async def test_create_message_translations_empty_translations(self, translation_service):
        """Test creating translations with empty translations dict."""
        # Act
        result = await translation_service.create_message_translations(
            message_id=123,
            translations={}
        )

        # Assert
        assert result == []

    async def test_translate_and_store_message_success(self, translation_service, mock_translator, mock_translation_repo):
        """Test complete translation workflow: translate and store."""
        # Arrange
        message_id = 123
        content = "Hello world"
        target_languages = ["de", "fr"]

        # Mock translator response
        translations = {"de": "Hallo Welt", "fr": "Bonjour le monde"}
        mock_translator.translate_to_multiple_languages.return_value = translations

        # Mock repository response
        created_objects = [
            MessageTranslation(message_id=123, target_language="de", content="Hallo Welt"),
            MessageTranslation(message_id=123, target_language="fr", content="Bonjour le monde"),
        ]
        mock_translation_repo.bulk_create_translations.return_value = created_objects

        # Act
        result = await translation_service.translate_and_store_message(
            message_id=message_id,
            content=content,
            target_languages=target_languages,
            source_language="en"
        )

        # Assert
        assert result == 2  # Number of translations created

        # Verify translator was called correctly
        mock_translator.translate_to_multiple_languages.assert_called_once_with(
            text=content,
            target_languages=target_languages,
            source_language="en"
        )

        # Verify repository was called to store translations
        mock_translation_repo.bulk_create_translations.assert_called_once()

    async def test_translate_and_store_message_no_translations(self, translation_service, mock_translator):
        """Test translate and store when no translations are returned."""
        # Arrange
        mock_translator.translate_to_multiple_languages.return_value = {}

        # Act
        result = await translation_service.translate_and_store_message(
            message_id=123,
            content="Hello world",
            target_languages=["de"]
        )

        # Assert
        assert result == 0

    async def test_translate_and_store_message_translation_error(self, translation_service, mock_translator):
        """Test translate and store handles translation errors gracefully."""
        # Arrange
        mock_translator.translate_to_multiple_languages.side_effect = TranslationError("API Error")

        # Act
        result = await translation_service.translate_and_store_message(
            message_id=123,
            content="Hello world",
            target_languages=["de"]
        )

        # Assert
        assert result == 0

    async def test_get_message_translation_found(self, translation_service, mock_translation_repo):
        """Test retrieving existing translation when found."""
        # Arrange
        message_id = 123
        target_language = "de"
        expected_content = "Hallo Welt"

        mock_translation = MessageTranslation(
            message_id=message_id,
            target_language=target_language,
            content=expected_content
        )
        mock_translation_repo.get_by_message_and_language.return_value = mock_translation

        # Act
        result = await translation_service.get_message_translation(
            message_id=message_id,
            target_language=target_language
        )

        # Assert
        assert result == expected_content
        mock_translation_repo.get_by_message_and_language.assert_called_once_with(
            message_id=message_id,
            target_language="DE"  # Should be uppercased
        )

    async def test_get_message_translation_not_found(self, translation_service, mock_translation_repo):
        """Test retrieving translation when not found."""
        # Arrange
        mock_translation_repo.get_by_message_and_language.return_value = None

        # Act
        result = await translation_service.get_message_translation(
            message_id=123,
            target_language="de"
        )

        # Assert
        assert result is None

    async def test_get_all_message_translations(self, translation_service, mock_translation_repo):
        """Test retrieving all translations for a message."""
        # Arrange
        message_id = 123
        translations = [
            MessageTranslation(message_id=123, target_language="DE", content="Hallo Welt"),
            MessageTranslation(message_id=123, target_language="FR", content="Bonjour le monde"),
        ]
        mock_translation_repo.get_by_message_id.return_value = translations

        # Act
        result = await translation_service.get_all_message_translations(message_id)

        # Assert
        expected = {"DE": "Hallo Welt", "FR": "Bonjour le monde"}
        assert result == expected
        mock_translation_repo.get_by_message_id.assert_called_once_with(message_id)

    async def test_delete_message_translations(self, translation_service, mock_translation_repo):
        """Test deleting all translations for a message."""
        # Arrange
        message_id = 123
        mock_translation_repo.delete_by_message_id.return_value = 3

        # Act
        result = await translation_service.delete_message_translations(message_id)

        # Assert
        assert result == 3
        mock_translation_repo.delete_by_message_id.assert_called_once_with(message_id)