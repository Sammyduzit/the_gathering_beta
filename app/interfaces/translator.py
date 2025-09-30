"""
Translator interface for text translation services.

This interface abstracts translation functionality, allowing different
translation providers (DeepL, Google Translate, etc.) to be used
interchangeably through dependency injection.
"""

from abc import ABC, abstractmethod


class TranslatorInterface(ABC):
    """Abstract interface for text translation services."""

    @abstractmethod
    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str | None = None
    ) -> str:
        """
        Translate text to target language.

        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'de', 'fr')
            source_language: Source language code (auto-detect if None)

        Returns:
            Translated text

        Raises:
            TranslationError: If translation fails
        """
        pass

    @abstractmethod
    async def translate_to_multiple_languages(
        self,
        text: str,
        target_languages: list[str],
        source_language: str | None = None
    ) -> dict[str, str]:
        """
        Translate text to multiple target languages.

        Args:
            text: Text to translate
            target_languages: List of target language codes
            source_language: Source language code (auto-detect if None)

        Returns:
            Dictionary mapping language codes to translated text
            Example: {'de': 'Hallo', 'fr': 'Bonjour'}

        Raises:
            TranslationError: If translation fails
        """
        pass

    @abstractmethod
    async def detect_language(self, text: str) -> str:
        """
        Detect the language of given text.

        Args:
            text: Text to analyze

        Returns:
            Detected language code

        Raises:
            TranslationError: If detection fails
        """
        pass

    @abstractmethod
    def get_supported_languages(self) -> list[str]:
        """
        Get list of supported language codes.

        Returns:
            List of supported language codes
        """
        pass

    @abstractmethod
    async def check_availability(self) -> bool:
        """
        Check if translation service is available.

        Returns:
            True if service is available, False otherwise
        """
        pass


class TranslationError(Exception):
    """Exception raised when translation operations fail."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error