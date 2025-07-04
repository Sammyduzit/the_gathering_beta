from fastapi import Depends

from app.services.conversation_service import ConversationService
from app.services.room_service import RoomService
from app.services.translation_service import TranslationService
from app.repositories.conversation_repository import IConversationRepository
from app.repositories.message_repository import IMessageRepository
from app.repositories.user_repository import IUserRepository
from app.repositories.room_repository import IRoomRepository
from app.repositories.repository_dependencies import (
    get_conversation_repository,
    get_message_repository,
    get_user_repository,
    get_room_repository,
)


def get_translation_service(
        message_repo: IMessageRepository = Depends(get_message_repository)
) -> TranslationService:
    """
    Create TranslationService instance with repository dependencies
    :param message_repo: Message repository instance
    :return: TranslationService instance
    """
    return TranslationService(message_repo=message_repo)

def get_conversation_service(
    conversation_repo: IConversationRepository = Depends(get_conversation_repository),
    message_repo: IMessageRepository = Depends(get_message_repository),
    user_repo: IUserRepository = Depends(get_user_repository),
    translation_service: TranslationService = Depends(get_translation_service),
) -> ConversationService:
    """
    Create ConversationService instance with repository dependencies.
    :param conversation_repo: Conversation repository instance
    :param message_repo: Message repository instance
    :param user_repo: User repository instance
    :param translation_service: Translation service instance
    :return: ConversationService instance
    """
    return ConversationService(
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        user_repo=user_repo,
        translation_service=translation_service,
    )


def get_room_service(
    room_repo: IRoomRepository = Depends(get_room_repository),
    user_repo: IUserRepository = Depends(get_user_repository),
    message_repo: IMessageRepository = Depends(get_message_repository),
    conversation_repo: IConversationRepository = Depends(get_conversation_repository),
    translation_service: TranslationService = Depends(get_translation_service),
) -> RoomService:
    """
    Create RoomService instance with repository dependencies.
    :param room_repo: Room repository instance
    :param user_repo: User repository instance
    :param message_repo: Message repository instance
    :param conversation_repo: Conversation repository instance
    :param translation_service: Translation service instance
    :return: RoomService instance
    """
    return RoomService(
        room_repo=room_repo,
        user_repo=user_repo,
        message_repo=message_repo,
        conversation_repo=conversation_repo,
        translation_service=translation_service,
    )
