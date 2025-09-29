from abc import abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.conversation import Conversation, ConversationType
from app.models.conversation_participant import ConversationParticipant
from app.models.user import User
from app.repositories.base_repository import BaseRepository


class IConversationRepository(BaseRepository[Conversation]):
    """Abstract interface for Conversation repository."""

    @abstractmethod
    async def create_private_conversation(
        self, room_id: int, participant_ids: list[int]
    ) -> Conversation:
        """Create a private conversation (2 participants)."""
        pass

    @abstractmethod
    async def create_group_conversation(
        self, room_id: int, participant_ids: list[int]
    ) -> Conversation:
        """Create a group conversation (3+ participants)."""
        pass

    @abstractmethod
    async def add_participant(
        self, conversation_id: int, user_id: int
    ) -> ConversationParticipant:
        """Add participant to conversation."""
        pass

    @abstractmethod
    async def remove_participant(self, conversation_id: int, user_id: int) -> bool:
        """Remove participant from conversation (set left_at)."""
        pass

    @abstractmethod
    async def is_participant(self, conversation_id: int, user_id: int) -> bool:
        """Check if user is active participant in conversation."""
        pass

    @abstractmethod
    async def get_participants(self, conversation_id: int) -> list[User]:
        """Get all active participants in conversation."""
        pass

    @abstractmethod
    async def get_user_conversations(self, user_id: int) -> list[Conversation]:
        """Get all active conversations for a user."""
        pass

    @abstractmethod
    async def get_room_conversations(self, room_id: int) -> list[Conversation]:
        """Get all active conversations in a room."""
        pass


class ConversationRepository(IConversationRepository):
    """SQLAlchemy implementation of Conversation repository."""

    def __init__(self, db: AsyncSession):
        """
        Initialize with async database session.
        :param db: SQLAlchemy async database session
        """
        super().__init__(db)

    async def get_by_id(self, id: int) -> Conversation | None:
        """Get conversation by ID."""
        query = select(Conversation).where(
            and_(Conversation.id == id, Conversation.is_active.is_(True))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_private_conversation(
        self, room_id: int, participant_ids: list[int]
    ) -> Conversation:
        """Create a private conversation (2 participants)."""
        if len(participant_ids) != 2:
            raise ValueError("Private conversations require exactly 2 participants")

        new_conversation = Conversation(
            room_id=room_id,
            conversation_type=ConversationType.PRIVATE,
            max_participants=2,
        )

        self.db.add(new_conversation)
        await self.db.flush()

        # Add participants
        for user_id in participant_ids:
            participant = ConversationParticipant(
                conversation_id=new_conversation.id, user_id=user_id
            )
            self.db.add(participant)

        await self.db.commit()
        await self.db.refresh(new_conversation)
        return new_conversation

    async def create_group_conversation(
        self, room_id: int, participant_ids: list[int]
    ) -> Conversation:
        """Create a group conversation (3+ participants)."""
        if len(participant_ids) < 2:
            raise ValueError("Group conversations require at least 2 participants")

        new_conversation = Conversation(
            room_id=room_id,
            conversation_type=ConversationType.GROUP,
            max_participants=None,
        )

        self.db.add(new_conversation)
        await self.db.flush()

        # Add participants
        for user_id in participant_ids:
            participant = ConversationParticipant(
                conversation_id=new_conversation.id, user_id=user_id
            )
            self.db.add(participant)

        await self.db.commit()
        await self.db.refresh(new_conversation)
        return new_conversation

    async def add_participant(
        self, conversation_id: int, user_id: int
    ) -> ConversationParticipant:
        """Add participant to conversation."""
        if await self.is_participant(conversation_id, user_id):
            raise ValueError("User is already a participant in this conversation")

        participant = ConversationParticipant(
            conversation_id=conversation_id, user_id=user_id
        )

        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(participant)
        return participant

    async def remove_participant(self, conversation_id: int, user_id: int) -> bool:
        """Remove participant from conversation (set left_at)."""
        participant_query = select(ConversationParticipant).where(
            and_(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        result = await self.db.execute(participant_query)
        participant = result.scalar_one_or_none()

        if participant:
            from datetime import datetime

            participant.left_at = datetime.now()
            await self.db.commit()
            return True
        return False

    async def is_participant(self, conversation_id: int, user_id: int) -> bool:
        """Check if user is active participant in conversation."""
        participant_query = select(ConversationParticipant).where(
            and_(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        result = await self.db.execute(participant_query)
        participant = result.scalar_one_or_none()
        return participant is not None

    async def get_participants(self, conversation_id: int) -> list[User]:
        """Get all active participants in conversation."""
        participants_query = (
            select(User)
            .join(
                ConversationParticipant,
                and_(
                    ConversationParticipant.user_id == User.id,
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.left_at.is_(None),
                ),
            )
            .where(User.is_active.is_(True))
        )

        result = await self.db.execute(participants_query)
        return list(result.scalars().all())

    async def get_user_conversations(self, user_id: int) -> list[Conversation]:
        """Get all active conversations for a user."""
        conversations_query = (
            select(Conversation)
            .join(
                ConversationParticipant,
                and_(
                    ConversationParticipant.conversation_id == Conversation.id,
                    ConversationParticipant.user_id == user_id,
                    ConversationParticipant.left_at.is_(None),
                ),
            )
            .where(Conversation.is_active.is_(True))
        )

        result = await self.db.execute(conversations_query)
        return list(result.scalars().all())

    async def get_room_conversations(self, room_id: int) -> list[Conversation]:
        """Get all active conversations in a room."""
        query = select(Conversation).where(
            and_(Conversation.room_id == room_id, Conversation.is_active.is_(True))
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Conversation]:
        """Get all conversations with pagination."""
        query = select(Conversation).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, conversation: Conversation) -> Conversation:
        """Create new conversation."""
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def update(self, conversation: Conversation) -> Conversation:
        """Update existing conversation."""
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def delete(self, id: int) -> bool:
        """Soft delete conversation (set inactive)."""
        conversation = await self.get_by_id(id)
        if conversation:
            conversation.is_active = False
            await self.db.commit()
            return True
        return False

    async def exists(self, id: int) -> bool:
        """Check if conversation exists by ID."""
        conversation = await self.get_by_id(id)
        return conversation is not None
