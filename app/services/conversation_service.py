from fastapi import HTTPException, status

from app.models.message import Message
from app.models.conversation import Conversation
from app.models.user import User
from app.repositories.conversation_repository import IConversationRepository
from app.repositories.message_repository import IMessageRepository
from app.repositories.user_repository import IUserRepository


class ConversationService:
    """Service for conversation business logic using Repository Pattern."""

    def __init__(
        self,
        conversation_repo: IConversationRepository,
        message_repo: IMessageRepository,
        user_repo: IUserRepository,
    ):
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.user_repo = user_repo

    def create_conversation(
        self,
        current_user: User,
        participant_usernames: list[str],
        conversation_type: str,
    ) -> Conversation:
        """
        Create private or group conversation with validation.
        :param current_user: User creating the conversation
        :param participant_usernames: List of participant usernames
        :param conversation_type: 'private' or 'group'
        :return: Created conversation
        """
        if not current_user.current_room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User must be in a room to create conversations",
            )

        if conversation_type == "private" and len(participant_usernames) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Private conversations require exactly 1 other participant",
            )

        if conversation_type == "group" and len(participant_usernames) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group conversations require at least 1 other participant",
            )

        participant_users = self._validate_participants(
            participant_usernames, current_user.current_room_id
        )

        all_participant_ids = [current_user.id] + [
            user.id for user in participant_users
        ]

        if conversation_type == "private":
            return self.conversation_repo.create_private_conversation(
                room_id=current_user.current_room_id,
                participant_ids=all_participant_ids,
            )
        else:
            return self.conversation_repo.create_group_conversation(
                room_id=current_user.current_room_id,
                participant_ids=all_participant_ids,
            )

    def send_message(
        self, current_user: User, conversation_id: int, content: str
    ) -> Message:
        """
        Send message to conversation with validation.
        :param current_user: User sending the message
        :param conversation_id: Target conversation ID
        :param content: Message content
        :return: Created message
        """
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )

        if not self.conversation_repo.is_participant(conversation_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a participant in this conversation",
            )

        message = self.message_repo.create_conversation_message(
            sender_id=current_user.id, conversation_id=conversation_id, content=content
        )

        message.sender_username = current_user.username
        return message

    def get_messages(
        self,
        current_user: User,
        conversation_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Message], int]:
        """
        Get conversation messages with validation and pagination.
        :param current_user: User requesting messages
        :param conversation_id: Conversation ID
        :param page: Page number
        :param page_size: Messages per page
        :return: Tuple of (messages, total_count)
        """
        self._validate_conversation_access(current_user.id, conversation_id)

        return self.message_repo.get_conversation_messages(
            conversation_id=conversation_id, page=page, page_size=page_size
        )

    def get_user_conversations(self, user_id: int) -> list[dict]:
        """
        Get all active conversations for user with formatted response.
        :param user_id: User ID
        :return: List of formatted conversation data
        """
        conversations = self.conversation_repo.get_user_conversations(user_id)

        conversation_list = []
        for conv in conversations:
            participants = self.conversation_repo.get_participants(conv.id)
            participant_names = [p.username for p in participants if p.id != user_id]

            conversation_list.append(
                {
                    "id": conv.id,
                    "type": conv.conversation_type.value,
                    "room_id": conv.room_id,
                    "participants": participant_names,
                    "participant_count": len(participants),
                    "created_at": conv.created_at,
                }
            )

        return conversation_list

    def get_participants(self, current_user: User, conversation_id: int) -> list[dict]:
        """
        Get conversation participants with validation.
        :param current_user: User requesting participants
        :param conversation_id: Conversation ID
        :return: List of formatted participant data
        """
        self._validate_conversation_access(current_user.id, conversation_id)

        participants = self.conversation_repo.get_participants(conversation_id)

        return [
            {
                "id": user.id,
                "username": user.username,
                "status": user.status.value,
                "avatar_url": user.avatar_url,
            }
            for user in participants
        ]

    def _validate_participants(self, usernames: list[str], room_id: int) -> list[User]:
        """
        Validate and return participant users.
        :param usernames: List of usernames to validate
        :param room_id: Room ID they should be in
        :return: List of validated User objects
        """
        participant_users = []
        for username in usernames:
            user = self.user_repo.get_by_username(username)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User '{username}' not found",
                )
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User '{username}' is not active",
                )
            if user.current_room_id != room_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User '{username}' is not in the same room",
                )
            participant_users.append(user)

        return participant_users

    def _validate_conversation_access(
        self, user_id: int, conversation_id: int
    ) -> Conversation:
        """
        Validate conversation exists and user has access.
        :param user_id: User ID
        :param conversation_id: Conversation ID
        :return: Conversation object
        """
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )

        if not self.conversation_repo.is_participant(conversation_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a participant in this conversation",
            )

        return conversation
