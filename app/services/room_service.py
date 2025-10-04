import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.constants import MAX_ROOM_MESSAGES, MESSAGE_CLEANUP_FREQUENCY
from app.models.message import Message
from app.models.room import Room
from app.models.user import User, UserStatus
from app.repositories.conversation_repository import IConversationRepository
from app.repositories.message_repository import IMessageRepository
from app.repositories.message_translation_repository import IMessageTranslationRepository
from app.repositories.room_repository import IRoomRepository
from app.repositories.user_repository import IUserRepository
from app.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


class RoomService:
    """Service for room business logic using Repository Pattern."""

    def __init__(
        self,
        room_repo: IRoomRepository,
        user_repo: IUserRepository,
        message_repo: IMessageRepository,
        conversation_repo: IConversationRepository,
        message_translation_repo: IMessageTranslationRepository,
        translation_service: TranslationService,
    ):
        self.room_repo = room_repo
        self.user_repo = user_repo
        self.message_repo = message_repo
        self.conversation_repo = conversation_repo
        self.message_translation_repo = message_translation_repo
        self.translation_service = translation_service

    async def get_all_rooms(self) -> list[Room]:
        """Get all active rooms."""
        return await self.room_repo.get_active_rooms()

    async def create_room(
        self,
        name: str,
        description: str | None,
        max_users: int | None,
        is_translation_enabled: bool = False,
    ) -> Room:
        """
        Create new room with validation.
        :param name: Room name
        :param description: Room description
        :param max_users: Maximum users allowed
        :return: Created room
        """
        if await self.room_repo.name_exists(name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room name '{name}' already exists",
            )

        new_room = Room(
            name=name,
            description=description,
            max_users=max_users,
            is_translation_enabled=is_translation_enabled,
        )

        return await self.room_repo.create(new_room)

    async def update_room(
        self,
        room_id: int,
        name: str,
        description: str | None,
        max_users: int | None,
        is_translation_enabled: bool = False,
    ) -> Room:
        """
        Update room with validation.
        :param room_id: Room ID to update
        :param name: New room name
        :param description: New room description
        :param max_users: New max users
        :return: Updated room
        """
        room = await self._get_room_or_404(room_id)

        if name != room.name and await self.room_repo.name_exists(name, room_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room name '{name}' already exists",
            )

        room.name = name
        room.description = description
        room.max_users = max_users
        room.is_translation_enabled = is_translation_enabled

        return await self.room_repo.update(room)

    async def delete_room(self, room_id: int) -> dict:
        """
        Soft delete room, kick out all users and deactivate conversations.
        :param room_id: Room ID to delete
        :return: Deleted room
        """
        room = await self._get_room_or_404(room_id)

        users_in_room = await self.room_repo.get_users_in_room(room_id)
        kicked_users = []
        for user in users_in_room:
            user.current_room_id = None
            user.status = UserStatus.AWAY
            await self.user_repo.update(user)
            kicked_users.append(user.username)

        conversations = await self.conversation_repo.get_room_conversations(room_id)
        deactivated_conversations = len(conversations)
        for conversation in conversations:
            conversation.is_active = False
            await self.conversation_repo.update(conversation)

        await self.room_repo.soft_delete(room_id)
        room.is_active = False

        return {
            "message": f"Room '{room.name}' has been closed",
            "room_id": room_id,
            "users_kicked": len(kicked_users),
            "conversations_archived": deactivated_conversations,
            "note": "Chat history remains accessible",
        }

    async def get_room_by_id(self, room_id: int) -> Room:
        """Get room by ID with validation."""
        return await self._get_room_or_404(room_id)

    async def get_room_count(self) -> dict:
        """Get count of active rooms."""
        active_rooms = await self.room_repo.get_active_rooms()
        room_count = len(active_rooms)

        return {
            "active_rooms": room_count,
            "message": f"Found {room_count} active rooms",
        }

    async def join_room(self, current_user: User, room_id: int) -> dict:
        """
        User joins room with validation.
        :param current_user: User joining room
        :param room_id: Room ID to join
        :return: Join confirmation
        """
        room = await self._get_room_or_404(room_id)

        current_user_count = await self.room_repo.get_user_count(room_id)
        if room.max_users and current_user_count >= room.max_users:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room '{room.name}' is full (max {room.max_users} users)",
            )

        current_user.current_room_id = room_id
        current_user.status = UserStatus.AVAILABLE
        await self.user_repo.update(current_user)

        final_user_count = await self.room_repo.get_user_count(room_id)

        return {
            "message": f"Successfully joined room '{room.name}'",
            "room_id": room_id,
            "room_name": room.name,
            "user_count": final_user_count,
        }

    async def leave_room(self, current_user: User, room_id: int) -> dict:
        """
        User leaves room with validation.
        :param current_user: User leaving room
        :param room_id: Room ID to leave
        :return: Leave confirmation
        """
        room = await self._get_room_or_404(room_id)

        if current_user.current_room_id != room_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User is not in room '{room.name}'",
            )

        current_user.current_room_id = None
        current_user.status = UserStatus.AWAY
        await self.user_repo.update(current_user)

        return {
            "message": f"Left room '{room.name}'",
            "room_id": room_id,
            "room_name": room.name,
        }

    async def get_room_users(self, room_id: int) -> dict:
        """
        Get users in room with validation.
        :param room_id: Room ID
        :return: Room users data
        """
        room = await self._get_room_or_404(room_id)
        users = await self.room_repo.get_users_in_room(room_id)

        room_users = [
            {
                "id": user.id,
                "username": user.username,
                "avatar_url": user.avatar_url,
                "status": user.status.value,
                "last_active": user.last_active,
            }
            for user in users
        ]

        return {
            "room_id": room_id,
            "room_name": room.name,
            "total_users": len(room_users),
            "users": room_users,
        }

    async def update_user_status(self, current_user: User, new_status: UserStatus) -> dict:
        """
        Update user status.
        :param current_user: User to update
        :param new_status: New status
        :return: Status update confirmation
        """
        current_user.status = new_status
        await self.user_repo.update(current_user)

        return {
            "message": f"Status updated to '{new_status.value}'",
            "new_status": new_status.value,
            "user": current_user.username,
        }

    async def send_room_message(self, current_user: User, room_id: int, content: str) -> Message:
        """
        Send message to room with validation.
        :param current_user: User sending message
        :param room_id: Target room ID
        :param content: Message content
        :return: Created message
        """
        room = await self._get_room_or_404(room_id)

        if current_user.current_room_id != room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User must be in room '{room.name}' to send messages",
            )

        message = await self.message_repo.create_room_message(
            room_id=room_id, content=content, sender_user_id=current_user.id
        )

        # Translation logic
        if room.is_translation_enabled:
            room_users = await self.room_repo.get_users_in_room(room_id)

            target_languages = list(
                set(
                    [
                        user.preferred_language.upper()
                        for user in room_users
                        if user.preferred_language
                        and user.preferred_language != current_user.preferred_language
                        and user.id != current_user.id
                    ]
                )
            )

            if target_languages:
                source_lang = current_user.preferred_language.upper() if current_user.preferred_language else None

                await self.translation_service.translate_and_store_message(
                    message_id=message.id,
                    content=content,
                    source_language=source_lang,
                    target_languages=target_languages,
                )

        # Periodic cleanup: Remove oldest messages when room messages exceed limit
        try:
            if message.id % MESSAGE_CLEANUP_FREQUENCY == 0:
                await self.message_repo.cleanup_old_room_messages(room_id, MAX_ROOM_MESSAGES)
        except SQLAlchemyError as e:
            logger.warning(f"Cleanup failed, but message sent successfully: {e}")

        message.sender_username = current_user.username
        return message

    async def get_room_messages(
        self, current_user: User, room_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list[Message], int]:
        """
        Get room messages with validation and pagination.
        :param current_user: User requesting messages
        :param room_id: Room ID
        :param page: Page number
        :param page_size: Messages per page
        :return: Tuple of (messages, total_count)
        """
        await self._get_room_or_404(room_id)

        if current_user.current_room_id != room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User must join the room before viewing messages",
            )

        messages, total_count = await self.message_repo.get_room_messages(
            room_id=room_id,
            page=page,
            page_size=page_size,
        )

        # Apply translations if user has preferred language
        if current_user.preferred_language:
            messages = await self._apply_translations_to_messages(messages, current_user.preferred_language)

        return messages, total_count

    async def _apply_translations_to_messages(self, messages: list[Message], user_language: str) -> list[Message]:
        """Apply translations to messages based on user's preferred language."""
        if not messages:
            return messages

        # Get all message IDs for batch translation lookup
        message_ids = [msg.id for msg in messages]

        # Batch query all translations for efficiency (avoid N+1 queries)
        translations = {}
        for message_id in message_ids:
            translation = await self.message_translation_repo.get_by_message_and_language(
                message_id, user_language.upper()
            )
            if translation:
                translations[message_id] = translation.content

        # Apply translations to messages
        for message in messages:
            if message.id in translations:
                message.content = translations[message.id]

        return messages

    async def _get_room_or_404(self, room_id: int) -> Room:
        """Get room by ID or raise 404."""
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room with id {room_id} not found",
            )
        return room
