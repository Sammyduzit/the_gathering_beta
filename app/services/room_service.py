from fastapi import HTTPException, status

from app.models.message import Message
from app.models.room import Room
from app.models.user import User, UserStatus
from app.repositories.conversation_repository import IConversationRepository
from app.repositories.room_repository import IRoomRepository
from app.repositories.user_repository import IUserRepository
from app.repositories.message_repository import IMessageRepository
from app.schemas.room_user_schemas import RoomUserResponse
from app.services.translation_service import TranslationService


class RoomService:
    """Service for room business logic using Repository Pattern."""

    def __init__(
        self,
        room_repo: IRoomRepository,
        user_repo: IUserRepository,
        message_repo: IMessageRepository,
        conversation_repo: IConversationRepository,
        translation_service: TranslationService
    ):
        self.room_repo = room_repo
        self.user_repo = user_repo
        self.message_repo = message_repo
        self.conversation_repo = conversation_repo
        self.translation_service = translation_service

    def get_all_rooms(self) -> list[Room]:
        """Get all active rooms."""
        return self.room_repo.get_active_rooms()

    def create_room(
        self, name: str, description: str | None, max_users: int | None
    ) -> Room:
        """
        Create new room with validation.
        :param name: Room name
        :param description: Room description
        :param max_users: Maximum users allowed
        :return: Created room
        """
        if self.room_repo.name_exists(name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room name '{name}' already exists",
            )

        new_room = Room(name=name, description=description, max_users=max_users)

        return self.room_repo.create(new_room)

    def update_room(
        self, room_id: int, name: str, description: str | None, max_users: int | None
    ) -> Room:
        """
        Update room with validation.
        :param room_id: Room ID to update
        :param name: New room name
        :param description: New room description
        :param max_users: New max users
        :return: Updated room
        """
        room = self._get_room_or_404(room_id)

        if name != room.name and self.room_repo.name_exists(name, room_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room name '{name}' already exists",
            )

        room.name = name
        room.description = description
        room.max_users = max_users

        return self.room_repo.update(room)

    def delete_room(self, room_id: int) -> dict:
        """
        Soft delete room, kick out all users and deactivate conversations.
        :param room_id: Room ID to delete
        :return: Deleted room
        """
        room = self._get_room_or_404(room_id)

        users_in_room = self.room_repo.get_users_in_room(room_id)
        kicked_users = []
        for user in users_in_room:
            user.current_room_id = None
            user.status = UserStatus.AWAY
            self.user_repo.update(user)
            kicked_users.append(user.username)

        conversations = self.conversation_repo.get_room_conversations(room_id)
        deactivated_conversations = len(conversations)
        for conversation in conversations:
            conversation.is_active = False
            self.conversation_repo.update(conversation)

        self.room_repo.soft_delete(room_id)
        room.is_active = False

        return {
            "message": f"Room '{room.name}' has been closed",
            "room_id": room_id,
            "users_kicked": len(kicked_users),
            "conversations_archived": deactivated_conversations,
            "note": "Chat history remains accessible",
        }

    def get_room_by_id(self, room_id: int) -> Room:
        """Get room by ID with validation."""
        return self._get_room_or_404(room_id)

    def get_room_count(self) -> dict:
        """Get count of active rooms."""
        active_rooms = self.room_repo.get_active_rooms()
        room_count = len(active_rooms)

        return {
            "active_rooms": room_count,
            "message": f"Found {room_count} active rooms",
        }

    def join_room(self, current_user: User, room_id: int) -> dict:
        """
        User joins room with validation.
        :param current_user: User joining room
        :param room_id: Room ID to join
        :return: Join confirmation
        """
        room = self._get_room_or_404(room_id)

        current_user_count = self.room_repo.get_user_count(room_id)
        if room.max_users and current_user_count >= room.max_users:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room '{room.name}' is full (max {room.max_users} users)",
            )

        current_user.current_room_id = room_id
        current_user.status = UserStatus.AVAILABLE
        self.user_repo.update(current_user)

        final_user_count = self.room_repo.get_user_count(room_id)

        return {
            "message": f"Successfully joined room '{room.name}'",
            "room_id": room_id,
            "room_name": room.name,
            "user_count": final_user_count,
        }

    def leave_room(self, current_user: User, room_id: int) -> dict:
        """
        User leaves room with validation.
        :param current_user: User leaving room
        :param room_id: Room ID to leave
        :return: Leave confirmation
        """
        room = self._get_room_or_404(room_id)

        if current_user.current_room_id != room_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User is not in room '{room.name}'",
            )

        current_user.current_room_id = None
        current_user.status = UserStatus.AWAY
        self.user_repo.update(current_user)

        return {
            "message": f"Left room '{room.name}'",
            "room_id": room_id,
            "room_name": room.name,
        }

    def get_room_users(self, room_id: int) -> dict:
        """
        Get users in room with validation.
        :param room_id: Room ID
        :return: Room users data
        """
        room = self._get_room_or_404(room_id)
        users = self.room_repo.get_users_in_room(room_id)

        room_users = [
            RoomUserResponse(
                id=user.id,
                username=user.username,
                status=user.status.value,
                last_active=user.last_active,
            )
            for user in users
        ]

        return {
            "room_id": room_id,
            "room_name": room.name,
            "total_users": len(room_users),
            "users": room_users,
        }

    def update_user_status(self, current_user: User, new_status: UserStatus) -> dict:
        """
        Update user status.
        :param current_user: User to update
        :param new_status: New status
        :return: Status update confirmation
        """
        current_user.status = new_status
        self.user_repo.update(current_user)

        return {
            "message": f"Status updated to '{new_status.value}'",
            "new_status": new_status.value,
            "user": current_user.username,
        }

    def send_room_message(
        self, current_user: User, room_id: int, content: str
    ) -> Message:
        """
        Send message to room with validation.
        :param current_user: User sending message
        :param room_id: Target room ID
        :param content: Message content
        :return: Created message
        """
        room = self._get_room_or_404(room_id)

        if current_user.current_room_id != room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User must be in room '{room.name}' to send messages",
            )

        message = self.message_repo.create_room_message(
            sender_id=current_user.id, room_id=room_id, content=content
        )

        room_users = self.room_repo.get_users_in_room(room_id)
        target_languages = list(set([
            user.preferred_language.upper()
            for user in room_users
            if user.preferred_language
        ]))

        if target_languages:
            self.translation_service.translate_and_store_message(
                message_id=message.id,
                content=content,
                target_languages=target_languages,
            )

        message.sender_username = current_user.username
        return message

    def get_room_messages(
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
        self._get_room_or_404(room_id)

        if current_user.current_room_id != room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User must join the room before viewing messages",
            )

        return self.message_repo.get_room_messages(
            room_id=room_id, page=page, page_size=page_size
        )

    def _get_room_or_404(self, room_id: int) -> Room:
        """Get room by ID or raise 404."""
        room = self.room_repo.get_by_id(room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room with id {room_id} not found",
            )
        return room
