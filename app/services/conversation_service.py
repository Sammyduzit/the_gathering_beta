from app.core.exceptions import (
    ConversationNotFoundException,
    ConversationValidationException,
    NotConversationParticipantException,
    UserNotFoundException,
    UserNotInRoomException,
)
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories.ai_entity_repository import IAIEntityRepository
from app.repositories.conversation_repository import IConversationRepository
from app.repositories.message_repository import IMessageRepository
from app.repositories.room_repository import IRoomRepository
from app.repositories.user_repository import IUserRepository
from app.services.translation_service import TranslationService


class ConversationService:
    """Service for conversation business logic using Repository Pattern."""

    def __init__(
        self,
        conversation_repo: IConversationRepository,
        message_repo: IMessageRepository,
        user_repo: IUserRepository,
        room_repo: IRoomRepository,
        translation_service: TranslationService,
        ai_entity_repo: IAIEntityRepository,
    ):
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.user_repo = user_repo
        self.room_repo = room_repo
        self.translation_service = translation_service
        self.ai_entity_repo = ai_entity_repo

    async def create_conversation(
        self,
        current_user: User,
        participant_usernames: list[str],
        conversation_type: str,
    ) -> Conversation:
        """
        Create private or group conversation with validation.
        Supports both human and AI participants.
        :param current_user: User creating the conversation
        :param participant_usernames: List of participant usernames (human or AI)
        :param conversation_type: 'private' or 'group'
        :return: Created conversation
        """
        if not current_user.current_room_id:
            raise UserNotInRoomException("User must be in a room to create conversations")

        if conversation_type == "private" and len(participant_usernames) != 1:
            raise ConversationValidationException("Private conversations require exactly 1 other participant")

        if conversation_type == "group" and len(participant_usernames) < 1:
            raise ConversationValidationException("Group conversations require at least 1 other participant")

        # Validate and separate human/AI participants
        human_participants, ai_participants = await self._validate_participants(
            participant_usernames, current_user.current_room_id
        )

        # Extract IDs
        user_ids = [current_user.id] + [user.id for user in human_participants]
        ai_ids = [ai.id for ai in ai_participants]

        # Create conversation with all participants at once
        if conversation_type == "private":
            conversation = await self.conversation_repo.create_private_conversation(
                room_id=current_user.current_room_id,
                user_ids=user_ids,
                ai_ids=ai_ids,
            )
        else:
            conversation = await self.conversation_repo.create_group_conversation(
                room_id=current_user.current_room_id,
                user_ids=user_ids,
                ai_ids=ai_ids,
            )

        return conversation

    async def send_message(
        self,
        current_user: User,
        conversation_id: int,
        content: str,
        in_reply_to_message_id: int | None = None,
    ) -> Message:
        """
        Send message to conversation with validation.
        :param current_user: User sending the message
        :param conversation_id: Target conversation ID
        :param content: Message content
        :param in_reply_to_message_id: Optional message to reply to
        :return: Created message
        """
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundException(conversation_id)

        if not await self.conversation_repo.is_participant(conversation_id, current_user.id):
            raise NotConversationParticipantException()

        message = await self.message_repo.create_conversation_message(
            conversation_id=conversation_id,
            content=content,
            sender_user_id=current_user.id,
            in_reply_to_message_id=in_reply_to_message_id,
        )

        # Load room async to check translation settings (avoid lazy loading)
        room = None
        if conversation.room_id:
            room = await self.room_repo.get_by_id(conversation.room_id)

        if room and room.is_translation_enabled:
            participants = await self.conversation_repo.get_participants(conversation_id)
            target_languages = list(
                {
                    participant.user.preferred_language.upper()
                    for participant in participants
                    if participant.user_id  # Only user participants, not AI
                    and participant.user.preferred_language
                    and participant.user.preferred_language != current_user.preferred_language
                    and participant.user_id != current_user.id
                }
            )

            if target_languages:
                source_lang = current_user.preferred_language.upper() if current_user.preferred_language else None

                await self.translation_service.translate_and_store_message(
                    message_id=message.id,
                    content=content,
                    source_language=source_lang,
                    target_languages=target_languages,
                )

        message.sender_username = current_user.username
        return message

    async def get_messages(
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
        await self._validate_conversation_access(current_user.id, conversation_id)

        messages, total_count = await self.message_repo.get_conversation_messages(
            conversation_id=conversation_id,
            page=page,
            page_size=page_size,
            user_language=current_user.preferred_language,
        )

        # Set sender_username for each message
        for message in messages:
            if message.sender_user_id:
                message.sender_username = message.sender_user.username
            elif message.sender_ai_id:
                message.sender_username = message.sender_ai.display_name

        return messages, total_count

    async def get_user_conversations(self, user_id: int) -> list[dict]:
        """
        Get all active conversations for user with formatted response.
        Includes room name, participant info, and latest message preview.
        :param user_id: User ID
        :return: List of formatted conversation data
        """
        conversations = await self.conversation_repo.get_user_conversations(user_id)

        conversation_list = []
        for conv in conversations:
            # Get participants
            participants = await self.conversation_repo.get_participants(conv.id)
            participant_names = [
                p.participant_name for p in participants if p.user_id != user_id or p.ai_entity_id is not None
            ]

            # Get room name
            room = await self.room_repo.get_by_id(conv.room_id)
            room_name = room.name if room else None

            # Get latest message for preview
            latest_message_obj = await self.message_repo.get_latest_conversation_message(conv.id)
            latest_message_at = latest_message_obj.sent_at if latest_message_obj else None
            latest_message_preview = (
                latest_message_obj.content[:50] + "..."
                if latest_message_obj and len(latest_message_obj.content) > 50
                else latest_message_obj.content
                if latest_message_obj
                else None
            )

            conversation_list.append(
                {
                    "id": conv.id,
                    "type": conv.conversation_type.value,
                    "room_id": conv.room_id,
                    "room_name": room_name,
                    "participants": participant_names,
                    "participant_count": len(participants),
                    "created_at": conv.created_at,
                    "latest_message_at": latest_message_at,
                    "latest_message_preview": latest_message_preview,
                }
            )

        return conversation_list

    async def get_participants(self, current_user: User, conversation_id: int) -> list[dict]:
        """
        Get conversation participants with validation.
        :param current_user: User requesting participants
        :param conversation_id: Conversation ID
        :return: List of formatted participant data
        """
        await self._validate_conversation_access(current_user.id, conversation_id)

        participants = await self.conversation_repo.get_participants(conversation_id)

        return [
            {
                "id": participant.user_id if participant.user_id else participant.ai_entity_id,
                "username": participant.participant_name,
                "status": participant.user.status.value if participant.user_id else "active",
                "avatar_url": participant.user.avatar_url if participant.user_id else None,
                "is_ai": participant.is_ai,
            }
            for participant in participants
        ]

    async def _validate_participants(self, usernames: list[str], room_id: int) -> tuple[list[User], list]:
        """
        Validate and separate human and AI participants.

        Logic:
        1. Try to find each username as human user first
        2. If not found, try to find as AI entity
        3. Validate that humans are in the same room
        4. Validate that AI entities are in the same room

        :param usernames: List of usernames (human or AI)
        :param room_id: Room ID for validation
        :return: Tuple of (human_users, ai_entities)
        """
        human_participants = []
        ai_participants = []

        for username in usernames:
            # Try human first
            user = await self.user_repo.get_by_username(username)
            if user:
                if not user.is_active:
                    raise ConversationValidationException(f"User '{username}' is not active")
                if user.current_room_id != room_id:
                    raise ConversationValidationException(f"User '{username}' is not in the same room")
                human_participants.append(user)
                continue

            # Try AI
            ai_entity = await self.ai_entity_repo.get_by_name(username)
            if ai_entity:
                if ai_entity.current_room_id != room_id:
                    raise ConversationValidationException(f"AI '{username}' is not in the same room")
                ai_participants.append(ai_entity)
                continue

            # Neither found
            raise UserNotFoundException(f"Participant '{username}' not found")

        return human_participants, ai_participants

    async def _validate_conversation_access(self, user_id: int, conversation_id: int) -> Conversation:
        """
        Validate conversation exists and user has access.
        :param user_id: User ID
        :param conversation_id: Conversation ID
        :return: Conversation object
        """
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundException(conversation_id)

        if not await self.conversation_repo.is_participant(conversation_id, user_id):
            raise NotConversationParticipantException()

        return conversation

    async def add_participant(
        self,
        conversation_id: int,
        username: str,
        current_user: User,
    ) -> dict:
        """
        Add participant to conversation (human or AI).

        Logic:
        1. Check if current_user is a participant.
        2. Try to find a Human user with the username.
        3. If not found, try to find an AI entity with the name.
        4. Add to the conversation.

        :param conversation_id: Conversation ID
        :param username: Username of human or name of AI entity
        :param current_user: User adding the participant
        :return: Success response with participant info
        """
        if not await self.conversation_repo.is_participant(conversation_id, current_user.id):
            raise NotConversationParticipantException()

        # Try Human first
        human_user = await self.user_repo.get_by_username(username)
        if human_user:
            await self.conversation_repo.add_participant(conversation_id, user_id=human_user.id)
            return {
                "message": f"User '{username}' added to conversation",
                "participant_type": "user",
                "participant_id": human_user.id,
            }

        # Try AI
        ai_entity = await self.ai_entity_repo.get_by_name(username)
        if ai_entity:
            await self.conversation_repo.add_participant(conversation_id, ai_entity_id=ai_entity.id)
            return {
                "message": f"Participant '{username}' added to conversation",
                "participant_type": "ai",
                "participant_id": ai_entity.id,
            }

        raise UserNotFoundException(f"Participant '{username}' not found")

    async def remove_participant(
        self,
        conversation_id: int,
        username: str,
        current_user: User,
    ) -> dict:
        """
        Remove participant from conversation.

        Logic:
        - Users can remove themselves (self-leave)
        - Only admins can remove other users or AI entities

        :param conversation_id: Conversation ID
        :param username: Username of human or name of AI entity
        :param current_user: User performing the removal
        :return: Success response with removal info
        """
        from app.core.exceptions import ForbiddenException

        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundException(conversation_id)

        # Check if user is removing themselves
        is_self_remove = username == current_user.username

        # Try Human first
        human_user = await self.user_repo.get_by_username(username)
        if human_user:
            # If not self-remove, require admin
            if not is_self_remove and not current_user.is_admin:
                raise ForbiddenException("Only admins can remove other participants")

            removed = await self.conversation_repo.remove_participant(conversation_id, user_id=human_user.id)
            if not removed:
                raise UserNotFoundException(f"User '{username}' is not a participant in this conversation")
            return {
                "message": f"User '{username}' removed from conversation",
                "participant_type": "user",
                "participant_id": human_user.id,
            }

        # Try AI (only admins can remove AI)
        ai_entity = await self.ai_entity_repo.get_by_name(username)
        if ai_entity:
            if not current_user.is_admin:
                raise ForbiddenException("Only admins can remove AI participants")

            removed = await self.conversation_repo.remove_participant(conversation_id, ai_entity_id=ai_entity.id)
            if not removed:
                raise UserNotFoundException(f"AI '{username}' is not a participant in this conversation")
            return {
                "message": f"Participant '{username}' removed from conversation",
                "participant_type": "ai",
                "participant_id": ai_entity.id,
            }

        raise UserNotFoundException(f"Participant '{username}' not found")

    async def get_conversation_detail(self, current_user: User, conversation_id: int) -> dict:
        """
        Get detailed conversation information including participants, permissions, and message metadata.
        :param current_user: User requesting conversation details
        :param conversation_id: Conversation ID
        :return: Detailed conversation data formatted for frontend
        """
        # Validate access
        await self._validate_conversation_access(current_user.id, conversation_id)

        # Get conversation
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundException(f"Conversation {conversation_id} not found")

        # Get participants with full details
        participants = await self.conversation_repo.get_participants(conversation_id)
        participant_details = [
            {
                "id": p.user_id if p.user_id else p.ai_entity_id,
                "username": p.participant_name,
                "avatar_url": p.user.avatar_url if p.user_id else None,
                "status": p.user.status.value if p.user_id else "online",
                "is_ai": p.is_ai,
            }
            for p in participants
        ]

        # Get room name
        room = await self.room_repo.get_by_id(conversation.room_id)
        room_name = room.name if room else None

        # Get message metadata
        message_count = await self.message_repo.count_conversation_messages(conversation_id)
        latest_message_obj = await self.message_repo.get_latest_conversation_message(conversation_id)

        # Format latest message
        latest_message = None
        if latest_message_obj:
            latest_message = {
                "id": latest_message_obj.id,
                "sender_id": latest_message_obj.sender_user_id or latest_message_obj.sender_ai_id,
                "sender_username": (
                    latest_message_obj.sender_user.username
                    if latest_message_obj.sender_user_id
                    else latest_message_obj.sender_ai.name
                ),
                "content": latest_message_obj.content,
                "sent_at": latest_message_obj.sent_at,
                "room_id": latest_message_obj.room_id,
                "conversation_id": latest_message_obj.conversation_id,
            }

        # Calculate permissions
        is_participant = any(p.user_id == current_user.id for p in participants)
        permissions = {
            "can_post": is_participant,
            "can_manage_participants": current_user.is_admin or is_participant,
            "can_leave": is_participant,
        }

        return {
            "id": conversation.id,
            "type": conversation.conversation_type.value,
            "room_id": conversation.room_id,
            "room_name": room_name,
            "is_active": conversation.is_active,
            "created_at": conversation.created_at,
            "participants": participant_details,
            "participant_count": len(participants),
            "message_count": message_count,
            "latest_message": latest_message,
            "permissions": permissions,
        }
