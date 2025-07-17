import pytest
from unittest.mock import Mock, patch
from app.services.translation_service import TranslationService


@pytest.mark.unit
class TestTranslationService:
    """Unit tests for TranslationService with clean repository pattern"""

    @pytest.fixture
    def mock_repos(self):
        """Create mock repositories for testing"""
        return {
            "message_repo": Mock(),
            "translation_repo": Mock(),
        }

    @pytest.fixture
    def translation_service(self, mock_repos):
        """Create TranslationService with mocked repositories"""
        return TranslationService(
            message_repo=mock_repos["message_repo"],
            translation_repo=mock_repos["translation_repo"],
        )

    def test_translate_message_content_no_client(self, translation_service):
        """Test translation when DeepL client is not available"""
        # Mock the property to return None
        with patch.object(type(translation_service), "deepl_client", new=None):
            result = translation_service.translate_message_content(
                "Hello", None, ["DE", "FR"]
            )

        assert result == {}

    def test_translate_message_content_success(self, translation_service):
        """Test successful translation"""
        # Mock translation results
        mock_result_de = Mock()
        mock_result_de.text = "Hallo"
        mock_result_fr = Mock()
        mock_result_fr.text = "Bonjour"

        # Mock DeepL client
        mock_client = Mock()
        mock_client.translate_text.side_effect = [mock_result_de, mock_result_fr]

        # Mock the property correctly
        with patch.object(type(translation_service), "deepl_client", new=mock_client):
            result = translation_service.translate_message_content(
                "Hello", None, ["DE", "FR"]
            )

        assert result == {"DE": "Hallo", "FR": "Bonjour"}
        assert mock_client.translate_text.call_count == 2

    def test_create_message_translations_success(self, translation_service, mock_repos):
        """Test successful creation of message translations via repository"""
        translations = {"DE": "Hallo", "FR": "Bonjour"}

        # Mock successful bulk creation
        mock_translation_objects = [Mock(), Mock()]
        mock_repos[
            "translation_repo"
        ].bulk_create_translations.return_value = mock_translation_objects

        result = translation_service.create_message_translations(1, translations)

        # Verify repository was called correctly
        mock_repos["translation_repo"].bulk_create_translations.assert_called_once()
        call_args = mock_repos["translation_repo"].bulk_create_translations.call_args[
            0
        ][0]

        # Verify correct number of translation objects created
        assert len(call_args) == 2
        assert len(result) == 2

    def test_create_message_translations_repository_failure(
        self, translation_service, mock_repos
    ):
        """Test repository failure handling"""
        translations = {"DE": "Hallo"}

        # Mock repository failure
        mock_repos["translation_repo"].bulk_create_translations.return_value = []

        result = translation_service.create_message_translations(1, translations)

        # Verify empty result on repository failure
        assert len(result) == 0

    def test_create_message_translations_empty_input(
        self, translation_service, mock_repos
    ):
        """Test handling of empty translations"""
        result = translation_service.create_message_translations(1, {})

        # Verify repository is not called with empty input
        mock_repos["translation_repo"].bulk_create_translations.assert_not_called()
        assert len(result) == 0

    def test_translate_and_store_message_complete_workflow(
        self, translation_service, mock_repos
    ):
        """Test complete translation workflow with repository pattern"""
        # Mock translation generation
        with patch.object(
            translation_service,
            "translate_message_content",
            return_value={"DE": "Hallo", "FR": "Bonjour"},
        ) as mock_translate:
            # Mock storage via repository
            with patch.object(
                translation_service,
                "create_message_translations",
                return_value=[Mock(), Mock()],
            ) as mock_store:
                result = translation_service.translate_and_store_message(
                    1, "Hello", None, ["DE", "FR"]
                )

                assert result == 2
                mock_translate.assert_called_once_with(
                    content="Hello", source_language=None, target_languages=["DE", "FR"]
                )
                mock_store.assert_called_once_with(
                    message_id=1, translations={"DE": "Hallo", "FR": "Bonjour"}
                )

    def test_translate_and_store_message_no_translations(self, translation_service):
        """Test workflow when no translations are generated"""
        with patch.object(
            translation_service, "translate_message_content", return_value={}
        ):
            result = translation_service.translate_and_store_message(
                1, "Hello", None, ["DE", "FR"]
            )

            assert result == 0

    def test_get_message_translation_success(self, translation_service, mock_repos):
        """Test retrieving message translation via repository"""
        # Mock translation object
        mock_translation = Mock()
        mock_translation.content = "Hallo"
        mock_repos[
            "translation_repo"
        ].get_by_message_and_language.return_value = mock_translation

        result = translation_service.get_message_translation(1, "DE")

        assert result == "Hallo"
        mock_repos[
            "translation_repo"
        ].get_by_message_and_language.assert_called_once_with(
            message_id=1, target_language="DE"
        )

    def test_get_message_translation_not_found(self, translation_service, mock_repos):
        """Test retrieving translation when not found"""
        mock_repos["translation_repo"].get_by_message_and_language.return_value = None

        result = translation_service.get_message_translation(1, "DE")

        assert result is None

    def test_get_all_message_translations(self, translation_service, mock_repos):
        """Test retrieving all translations for a message"""
        # Mock translation objects
        mock_translations = [
            Mock(target_language="DE", content="Hallo"),
            Mock(target_language="FR", content="Bonjour"),
        ]
        mock_repos[
            "translation_repo"
        ].get_by_message_id.return_value = mock_translations

        result = translation_service.get_all_message_translations(1)

        assert result == {"DE": "Hallo", "FR": "Bonjour"}
        mock_repos["translation_repo"].get_by_message_id.assert_called_once_with(1)

    def test_delete_message_translations(self, translation_service, mock_repos):
        """Test deleting message translations via repository"""
        mock_repos["translation_repo"].delete_by_message_id.return_value = 2

        result = translation_service.delete_message_translations(1)

        assert result == 2
        mock_repos["translation_repo"].delete_by_message_id.assert_called_once_with(1)
