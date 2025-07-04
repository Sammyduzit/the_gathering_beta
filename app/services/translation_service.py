import deepl

from app.core.config import settings
from app.models.message_translation import MessageTranslation
from app.repositories.message_repository import IMessageRepository


class TranslationService:
    """Service for DeepL translation API integration"""

    def __init__(self, message_repo: IMessageRepository):
        self.message_repo = message_repo
        self._deepl_client: deepl.DeepLClient | None = None

    @property
    def deepl_client(self) -> deepl.DeepLClient | None:
        """
        Lazy-loaded DeepL client with error handling.
        :return: DeepL client or None if initialization fails
        """
        if self._deepl_client is None:
            try:
                if not settings.deepl_api_key:
                    print("DEEPL_API_KEY not configured - translations disabled")
                    return None

                self._deepl_client = deepl.DeepLClient(settings.deepl_api_key)
                self._deepl_client.set_app_info("the-gathering", "1.0.0")
                print("DeepL client initialized successfully")

            except Exception as e:
                print(f"Failed to initialize DeepL client: {e}")
                return None

        return self._deepl_client

    def translate_message_content(
        self,
        content: str,
        source_language: str | None = None,
        target_languages: list[str] | None = None,
    ) -> dict[str, str]:
        """
        Translate message content to multiple target languages.
        :param content: Original message content
        :param source_language: Source language (auto-detect if None)
        :param target_languages: List of target language codes
        :return: Dictionary mapping language codes to translated content
        """
        if not self.deepl_client:
            print("DeepL client not available - skipping translation")
            return {}

        if not target_languages:
            print("No target languages specified - skipping translation")
            return {}

        if source_language and source_language.upper() in target_languages:
            target_languages.remove(source_language.upper())

        translations = {}

        for target_lang in target_languages:
            try:
                print(f"Translating to {target_lang}")

                result = self.deepl_client.translate_text(
                    content, source_lang=source_language, target_lang=target_lang
                )

                if not result.text or not result.text.strip():
                    print(f"DeepL returned empty translation for {target_lang}")
                    continue

                translations[target_lang] = result.text
                print(f"Successfully translated to {target_lang}")

            except deepl.DeepLException as e:
                print(f"DeepL API error for {target_lang}: {e}")
                continue
            except Exception as e:
                print(f"Unexpected error translating to {target_lang}: {e}")
                continue

        print(
            f"Translation summary: {len(translations)}/{len(target_languages)} successful"
        )
        return translations

    def create_message_translations(
        self, message_id: int, translations: dict[str, str]
    ) -> list[MessageTranslation]:
        """
        Store translations in database.
        :param message_id: ID of the original message
        :param translations: Dictionary mapping language codes to translated content
        :return: List of created MessageTranslation objects
        """
        if not translations:
            return []

        created_translations = []

        for target_language, translated_content in translations.items():
            try:
                translation = MessageTranslation(
                    message_id=message_id,
                    target_language=target_language,
                    content=translated_content,
                )

                created_translations.append(translation)

            except Exception as e:
                print(f"Failed to create translation for {target_language}: {e}")
                continue

        return created_translations

    def translate_and_store_message(
        self,
        message_id: int,
        content: str,
        source_language: str | None = None,
        target_languages: list[str] | None = None,
    ) -> int:
        """
        Complete translation workflow: translate content and store in database.
        :param message_id: ID of the message to translate
        :param content: Original message content
        :param source_language: Source language code (auto-detect if None)
        :param target_languages: Target language codes
        :return: Number of successful translations created
        """
        try:
            translations = self.translate_message_content(
                content=content,
                source_language=source_language,
                target_languages=target_languages,
            )

            if not translations:
                print(f"No translations created for message {message_id}")
                return 0

            translation_objects = self.create_message_translations(
                message_id=message_id, translations=translations
            )

            print(
                f"Created {len(translation_objects)} translations for message {message_id}"
            )
            return len(translation_objects)

        except Exception as e:
            print(f"Translation workflow failed for message {message_id}: {e}")
            return 0

    def get_message_translation(
        self, message_id: int, target_language: str
    ) -> str | None:
        """
        Retrieve specific translation from database.
        :param message_id: ID of the original message
        :param target_language: Target language code
        :return: Translated content or None if not found
        """
        pass
