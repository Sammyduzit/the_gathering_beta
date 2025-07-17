from abc import abstractmethod
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.models.message_translation import MessageTranslation
from app.repositories.base_repository import BaseRepository


class IMessageTranslationRepository(BaseRepository[MessageTranslation]):
    """Abstract interface for MessageTranslation repository."""

    @abstractmethod
    def create_translation(
        self, message_id: int, target_language: str, content: str
    ) -> MessageTranslation:
        """Create a new message translation."""
        pass

    @abstractmethod
    def get_by_message_and_language(
        self, message_id: int, target_language: str
    ) -> Optional[MessageTranslation]:
        """Get translation for specific message and language."""
        pass

    @abstractmethod
    def get_by_message_id(self, message_id: int) -> List[MessageTranslation]:
        """Get all translations for a message."""
        pass

    @abstractmethod
    def delete_by_message_id(self, message_id: int) -> int:
        """Delete all translations for a message."""
        pass

    @abstractmethod
    def bulk_create_translations(
        self, translations: List[MessageTranslation]
    ) -> List[MessageTranslation]:
        """Create multiple translations in one transaction."""
        pass


class MessageTranslationRepository(IMessageTranslationRepository):
    """SQLAlchemy implementation of MessageTranslation repository."""

    def __init__(self, db: Session):
        """
        Initialize with database session.
        :param db: SQLAlchemy database session
        """
        super().__init__(db)

    def get_by_id(self, id: int) -> Optional[MessageTranslation]:
        """Get message translation by ID."""
        query = select(MessageTranslation).where(MessageTranslation.id == id)
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def create_translation(
        self, message_id: int, target_language: str, content: str
    ) -> MessageTranslation:
        """Create a new message translation."""
        new_translation = MessageTranslation(
            message_id=message_id,
            target_language=target_language.upper(),
            content=content,
        )

        self.db.add(new_translation)
        self.db.commit()
        self.db.refresh(new_translation)
        return new_translation

    def get_by_message_and_language(
        self, message_id: int, target_language: str
    ) -> Optional[MessageTranslation]:
        """Get translation for specific message and language."""
        query = select(MessageTranslation).where(
            and_(
                MessageTranslation.message_id == message_id,
                MessageTranslation.target_language == target_language.upper(),
            )
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def get_by_message_id(self, message_id: int) -> List[MessageTranslation]:
        """Get all translations for a message."""
        query = (
            select(MessageTranslation)
            .where(MessageTranslation.message_id == message_id)
            .order_by(MessageTranslation.target_language)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    def delete_by_message_id(self, message_id: int) -> int:
        """Delete all translations for a message."""
        translations = self.get_by_message_id(message_id)
        deleted_count = len(translations)

        for translation in translations:
            self.db.delete(translation)

        if deleted_count > 0:
            self.db.commit()

        return deleted_count

    def bulk_create_translations(
        self, translations: List[MessageTranslation]
    ) -> List[MessageTranslation]:
        """Create multiple translations in one transaction."""
        if not translations:
            return []

        try:
            for translation in translations:
                self.db.add(translation)

            self.db.commit()

            # Refresh all objects
            for translation in translations:
                self.db.refresh(translation)

            return translations

        except Exception as e:
            self.db.rollback()
            print(f"Failed to bulk create translations: {e}")
            return []

    def get_all(self, limit: int = 100, offset: int = 0) -> List[MessageTranslation]:
        """Get all message translations with pagination."""
        query = (
            select(MessageTranslation)
            .limit(limit)
            .offset(offset)
            .order_by(MessageTranslation.created_at.desc())
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    def create(self, translation: MessageTranslation) -> MessageTranslation:
        """Create new message translation."""
        self.db.add(translation)
        self.db.commit()
        self.db.refresh(translation)
        return translation

    def update(self, translation: MessageTranslation) -> MessageTranslation:
        """Update existing message translation."""
        self.db.commit()
        self.db.refresh(translation)
        return translation

    def delete(self, id: int) -> bool:
        """Delete message translation by ID."""
        translation = self.get_by_id(id)
        if translation:
            self.db.delete(translation)
            self.db.commit()
            return True
        return False

    def exists(self, id: int) -> bool:
        """Check if message translation exists by ID."""
        translation = self.get_by_id(id)
        return translation is not None
