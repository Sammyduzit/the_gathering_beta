from abc import abstractmethod
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.models.conversation import Conversation, ConversationType
from app.models.conversation_participant import ConversationParticipant
from app.models.user import User
from app.repositories.base_repository import BaseRepository


class IConversationRepository(BaseRepository[Conversation]):
    """Abstract interface for Conversation repository."""

    @abstractmethod
    def create_private_conversation(
        self, room_id: int, participant_ids: List[int]
    ) -> Conversation:
        """Create a private conversation (2 participants)."""
        pass

    @abstractmethod
    def create_group_conversation(
        self, room_id: int, participant_ids: List[int]
    ) -> Conversation:
        """Create a group conversation (3+ participants)."""
        pass

    @abstractmethod
    def add_participant(
        self, conversation_id: int, user_id: int
    ) -> ConversationParticipant:
        """Add participant to conversation."""
        pass

    @abstractmethod
    def remove_participant(self, conversation_id: int, user_id: int) -> bool:
        """Remove participant from conversation (set left_at)."""
        pass

    @abstractmethod
    def is_participant(self, conversation_id: int, user_id: int) -> bool:
        """Check if user is active participant in conversation."""
        pass

    @abstractmethod
    def get_participants(self, conversation_id: int) -> List[User]:
        """Get all active participants in conversation."""
        pass

    @abstractmethod
    def get_user_conversations(self, user_id: int) -> List[Conversation]:
        """Get all active conversations for a user."""
        pass

    @abstractmethod
    def get_room_conversations(self, room_id: int) -> List[Conversation]:
        """Get all active conversations in a room."""
        pass


class ConversationRepository(IConversationRepository):
    """SQLAlchemy implementation of Conversation repository."""

    def __init__(self, db: Session):
        """
        Initialize with database session.
        :param db: SQLAlchemy database session
        """
        super().__init__(db)

    def get_by_id(self, id: int) -> Optional[Conversation]:
        """Get conversation by ID."""
        query = select(Conversation).where(
            and_(Conversation.id == id, Conversation.is_active.is_(True))
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()

    def create_private_conversation(
        self, room_id: int, participant_ids: List[int]
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
        self.db.flush()

        # Add participants
        for user_id in participant_ids:
            participant = ConversationParticipant(
                conversation_id=new_conversation.id, user_id=user_id
            )
            self.db.add(participant)

        self.db.commit()
        self.db.refresh(new_conversation)
        return new_conversation

    def create_group_conversation(
        self, room_id: int, participant_ids: List[int]
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
        self.db.flush()

        # Add participants
        for user_id in participant_ids:
            participant = ConversationParticipant(
                conversation_id=new_conversation.id, user_id=user_id
            )
            self.db.add(participant)

        self.db.commit()
        self.db.refresh(new_conversation)
        return new_conversation

    def add_participant(
        self, conversation_id: int, user_id: int
    ) -> ConversationParticipant:
        """Add participant to conversation."""
        if self.is_participant(conversation_id, user_id):
            raise ValueError("User is already a participant in this conversation")

        participant = ConversationParticipant(
            conversation_id=conversation_id, user_id=user_id
        )

        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def remove_participant(self, conversation_id: int, user_id: int) -> bool:
        """Remove participant from conversation (set left_at)."""
        participant_query = select(ConversationParticipant).where(
            and_(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        result = self.db.execute(participant_query)
        participant = result.scalar_one_or_none()

        if participant:
            from datetime import datetime

            participant.left_at = datetime.now()
            self.db.commit()
            return True
        return False

    def is_participant(self, conversation_id: int, user_id: int) -> bool:
        """Check if user is active participant in conversation."""
        participant_query = select(ConversationParticipant).where(
            and_(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        result = self.db.execute(participant_query)
        participant = result.scalar_one_or_none()
        return participant is not None

    def get_participants(self, conversation_id: int) -> List[User]:
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

        result = self.db.execute(participants_query)
        return list(result.scalars().all())

    def get_user_conversations(self, user_id: int) -> List[Conversation]:
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

        result = self.db.execute(conversations_query)
        return list(result.scalars().all())

    def get_room_conversations(self, room_id: int) -> List[Conversation]:
        """Get all active conversations in a room."""
        query = select(Conversation).where(
            and_(Conversation.room_id == room_id, Conversation.is_active.is_(True))
        )
        result = self.db.execute(query)
        return list(result.scalars().all())

    def update(self, conversation: Conversation) -> Conversation:
        """Update existing conversation."""
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Conversation]:
        """Get all conversations with pagination."""
        query = select(Conversation).limit(limit).offset(offset)
        result = self.db.execute(query)
        return list(result.scalars().all())

    def create(self, conversation: Conversation) -> Conversation:
        """Create new conversation."""
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def update(self, conversation: Conversation) -> Conversation:
        """Update existing conversation."""
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def delete(self, id: int) -> bool:
        """Soft delete conversation (set inactive)."""
        conversation = self.get_by_id(id)
        if conversation:
            conversation.is_active = False
            self.db.commit()
            return True
        return False

    def exists(self, id: int) -> bool:
        """Check if conversation exists by ID."""
        conversation = self.get_by_id(id)
        return conversation is not None
