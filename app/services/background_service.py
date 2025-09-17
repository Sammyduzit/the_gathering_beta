import asyncio
import logging
from typing import Dict, List

from app.core.background_tasks import background_task_retry
from app.services.translation_service import TranslationService
from app.models.message import Message
from app.models.message_translation import MessageTranslation
from app.repositories.message_translation_repository import IMessageTranslationRepository

logger = logging.getLogger(__name__)


class BackgroundService:
    """Service for handling background tasks like translations and notifications."""

    def __init__(
        self,
        translation_service: TranslationService,
        message_translation_repo: IMessageTranslationRepository,
    ):
        self.translation_service = translation_service
        self.message_translation_repo = message_translation_repo

    @background_task_retry(max_retries=2, delay=2.0)
    async def process_message_translation_background(
        self,
        message: Message,
        target_languages: List[str],
        room_translation_enabled: bool = True
    ) -> Dict[str, str]:
        """
        Process message translation in background for multiple languages.
        :param message: Message to translate
        :param target_languages: List of target language codes
        :param room_translation_enabled: Whether room has translation enabled
        :return: Dictionary of language -> translated content
        """
        if not room_translation_enabled:
            logger.info(f"Translation disabled for room, skipping message {message.id}")
            return {}

        logger.info(f"Starting background translation for message {message.id} to {len(target_languages)} languages")

        translations = {}

        for target_lang in target_languages:
            try:
                # Check if translation already exists
                existing_translation = await self.message_translation_repo.get_translation(
                    message.id, target_lang
                )

                if existing_translation:
                    translations[target_lang] = existing_translation.content
                    logger.info(f"Using existing translation for message {message.id} -> {target_lang}")
                    continue

                # Create new translation
                translation_result = await self.translation_service.translate_message_content(
                    content=message.content,
                    target_language=target_lang,
                    source_language="auto"
                )

                if target_lang in translation_result:
                    content = translation_result[target_lang]

                    # Store translation in database
                    new_translation = MessageTranslation(
                        message_id=message.id,
                        content=content,
                        target_language=target_lang
                    )
                    await self.message_translation_repo.create(new_translation)

                    translations[target_lang] = content
                    logger.info(f"Successfully translated message {message.id} -> {target_lang}")

            except Exception as e:
                logger.error(f"Failed to translate message {message.id} to {target_lang}: {e}")
                continue

        logger.info(f"Background translation completed for message {message.id}: {len(translations)} translations")
        return translations

    @background_task_retry(max_retries=1, delay=1.0)
    async def cleanup_old_translations_background(self, days_old: int = 30) -> int:
        """
        Clean up old translations in background.
        :param days_old: Remove translations older than this many days
        :return: Number of cleaned up translations
        """
        logger.info(f"Starting cleanup of translations older than {days_old} days")

        try:
            # This would need to be implemented in the repository
            # cleaned_count = await self.message_translation_repo.cleanup_old_translations(days_old)
            # For now, just log the intention
            logger.info("Translation cleanup completed (placeholder)")
            return 0
        except Exception as e:
            logger.error(f"Translation cleanup failed: {e}")
            raise

    @background_task_retry(max_retries=1, delay=0.5)
    async def log_user_activity_background(
        self,
        user_id: int,
        activity_type: str,
        details: Dict[str, any] = None
    ) -> None:
        """
        Log user activity in background.
        :param user_id: User ID
        :param activity_type: Type of activity (message_sent, room_joined, etc.)
        :param details: Additional activity details
        """
        logger.info(f"Logging activity for user {user_id}: {activity_type}")

        try:
            # This could be extended to store in database or external service
            activity_details = details or {}
            logger.info(f"User {user_id} activity: {activity_type} - {activity_details}")
        except Exception as e:
            logger.error(f"Failed to log user activity: {e}")
            raise

    @background_task_retry(max_retries=2, delay=3.0)
    async def notify_room_users_background(
        self,
        room_id: int,
        message: str,
        exclude_user_ids: List[int] = None
    ) -> None:
        """
        Send notifications to room users in background.
        :param room_id: Room ID
        :param message: Notification message
        :param exclude_user_ids: User IDs to exclude from notification
        """
        exclude_user_ids = exclude_user_ids or []
        logger.info(f"Sending notifications to room {room_id} users (excluding {len(exclude_user_ids)} users)")

        try:
            # This would integrate with a notification service
            # For now, just log the intention
            logger.info(f"Room {room_id} notification: {message}")
        except Exception as e:
            logger.error(f"Failed to send room notifications: {e}")
            raise