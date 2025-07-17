from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.user_repository import UserRepository, IUserRepository
from app.repositories.room_repository import RoomRepository, IRoomRepository
from app.repositories.message_repository import MessageRepository, IMessageRepository
from app.repositories.message_translation_repository import MessageTranslationRepository, IMessageTranslationRepository
from app.repositories.conversation_repository import (
    ConversationRepository,
    IConversationRepository,
)


def get_user_repository(db: Session = Depends(get_db)) -> IUserRepository:
    """
    Create UserRepository instance with database session.
    :param db: Database session from get_db dependency
    :return: UserRepository instance
    """
    return UserRepository(db)


def get_room_repository(db: Session = Depends(get_db)) -> IRoomRepository:
    """
    Create RoomRepository instance with database session.
    :param db: Database session from get_db dependency
    :return: RoomRepository instance
    """
    return RoomRepository(db)


def get_message_repository(db: Session = Depends(get_db)) -> IMessageRepository:
    """
    Create MessageRepository instance with database session.
    :param db: Database session from get_db dependency
    :return: MessageRepository instance
    """
    return MessageRepository(db)


def get_conversation_repository(
    db: Session = Depends(get_db),
) -> IConversationRepository:
    """
    Create ConversationRepository instance with database session.
    :param db: Database session from get_db dependency
    :return: ConversationRepository instance
    """
    return ConversationRepository(db)


def get_message_translation_repository(
    db: Session = Depends(get_db),
) -> IMessageTranslationRepository:
    """
    Create MessageTranslationRepository instance with database session.
    :param db: Database session from get_db dependency
    :return: MessageTranslationRepository instance
    """
    return MessageTranslationRepository(db)